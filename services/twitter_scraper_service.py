import hashlib
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

ACCOUNT_WEIGHTS: Dict[str, float] = {
    "CNBCTV18News": 0.90,
    "CNBCTV18Live": 0.90,
    "NDTVProfitIndia": 0.80,
    "ETNOWlive": 0.85,
    "REDBOXINDIA": 0.75,
}

TARGET_ACCOUNTS = list(ACCOUNT_WEIGHTS.keys())
DEFAULT_TWEETS_PER_ACCOUNT = 20

NITTER_INSTANCES = [
    "https://nitter.tiekoetter.com",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.cz",
    "https://nitter.it",
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _weight_for(author: str) -> float:
    for handle, weight in ACCOUNT_WEIGHTS.items():
        if handle.lower() == author.lower():
            return weight
    return 0.70


def _make_id(text: str, author: str, created_at: str) -> str:
    raw = f"{author}:{created_at}:{text[:80]}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _parse_nitter_html(html: str, username: str, limit: int, source_label: str) -> List[dict]:
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    tweets = []
    for item in soup.select(".timeline-item")[:limit]:
        content_el = item.select_one(".tweet-content")
        time_el = item.select_one("time")
        if not content_el:
            continue
        text = content_el.get_text(separator=" ", strip=True)
        ts = (
            time_el["datetime"]
            if time_el and time_el.get("datetime")
            else datetime.now(timezone.utc).isoformat()
        )
        tweets.append({
            "tweet_id": _make_id(text, username, ts),
            "raw_text": text,
            "created_at": ts,
            "author": username,
            "account_weight": _weight_for(username),
            "source": source_label,
        })
    return tweets


def _fetch_account(username: str, limit: int) -> Tuple[List[dict], dict]:
    """Fetch tweets via Playwright → Nitter instances → x.com fallback."""
    from playwright.sync_api import TimeoutError as PWTimeout  # type: ignore
    from playwright.sync_api import sync_playwright

    debug: dict = {
        "account": username,
        "status": "INIT",
        "tweets_fetched": 0,
        "error": "",
        "source": "",
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            last_err = "no Nitter instance responded"

            for base in NITTER_INSTANCES:
                try:
                    page = browser.new_page(user_agent=_UA)
                    page.goto(f"{base}/{username}", timeout=20_000)
                    try:
                        page.wait_for_selector(".timeline-item, .error-panel", timeout=10_000)
                    except PWTimeout:
                        page.close()
                        last_err = f"{base}: timed out"
                        continue

                    tweets = _parse_nitter_html(
                        page.content(), username, limit,
                        source_label=f"nitter:{page.url.split('/')[2]}",
                    )
                    page.close()

                    if tweets:
                        browser.close()
                        debug.update(status="SUCCESS", tweets_fetched=len(tweets), source="playwright+nitter")
                        return tweets, debug

                    last_err = f"{base}: rendered but no tweets found"
                except Exception as e:
                    last_err = f"{base}: {e}"
                    try:
                        page.close()
                    except Exception:
                        pass
                    continue

            # Last resort: x.com directly (may show login wall)
            try:
                page = browser.new_page(user_agent=_UA)
                page.goto(f"https://x.com/{username}", timeout=30_000)
                try:
                    page.wait_for_selector("article", timeout=15_000)
                except PWTimeout:
                    page.close()
                    browser.close()
                    debug.update(status="FAILED", error=f"x.com login wall; nitter: {last_err}")
                    return [], debug

                articles = page.locator("article").all()
                tweets = []
                for article in articles[:limit]:
                    text = article.inner_text().strip()
                    if not text:
                        continue
                    ts = datetime.now(timezone.utc).isoformat()
                    try:
                        dt = article.locator("time").first.get_attribute("datetime", timeout=1_000)
                        if dt:
                            ts = dt
                    except Exception:
                        pass
                    tweets.append({
                        "tweet_id": _make_id(text, username, ts),
                        "raw_text": text,
                        "created_at": ts,
                        "author": username,
                        "account_weight": _weight_for(username),
                        "source": "playwright+xcom",
                    })
                page.close()
                browser.close()

                if tweets:
                    debug.update(status="SUCCESS", tweets_fetched=len(tweets), source="playwright+xcom")
                    return tweets, debug

                debug.update(status="FAILED", error=f"x.com: no articles; nitter: {last_err}")
                return [], debug

            except Exception as e:
                browser.close()
                debug.update(status="FAILED", error=str(e))
                return [], debug

    except Exception as e:
        debug.update(status="FAILED", error=str(e))
        return [], debug


# ── Error classification ──────────────────────────────────────────────────────

def classify_error(debug: dict) -> str:
    err = debug.get("error", "").lower()
    if "rate" in err:
        return "RATE_LIMIT"
    if "not found" in err or "no user" in err:
        return "INVALID_USERNAME"
    if "login" in err or "auth" in err:
        return "AUTH_REQUIRED"
    if debug.get("tweets_fetched", 0) == 0:
        return "EMPTY_RESPONSE"
    return "UNKNOWN"


def analyze_fetch(debug_logs: List[dict]) -> List[dict]:
    return [
        {"account": d["account"], "issue": classify_error(d)}
        for d in debug_logs
        if d.get("status") != "SUCCESS"
    ]


# ── Public interface ──────────────────────────────────────────────────────────

def fetch_tweets() -> Tuple[List[dict], List[dict]]:
    """Fetch tweets via Playwright+Nitter for all target accounts.
    Returns (tweets, debug_logs)."""
    limit = int(os.getenv("TWEETS_PER_ACCOUNT", str(DEFAULT_TWEETS_PER_ACCOUNT)))
    all_tweets: List[dict] = []
    debug_logs: List[dict] = []

    for account in TARGET_ACCOUNTS:
        tweets, debug = _fetch_account(account, limit)
        all_tweets.extend(tweets)
        debug_logs.append(debug)
        print(f"[SCRAPER] {account}: {debug['status']} ({debug['tweets_fetched']} tweets)")

    issues = analyze_fetch(debug_logs)
    for issue in issues:
        print(f"[SCRAPER] WARNING — {issue['account']}: {issue['issue']}")

    return all_tweets, debug_logs
