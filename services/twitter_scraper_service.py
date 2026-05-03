import asyncio
import os
from datetime import datetime, timezone
from typing import List, Dict

ACCOUNT_WEIGHTS: Dict[str, float] = {
    "CNBCTV18News": 0.90,
    "NDTVProfitIndia": 0.80,
    "ETNOWlive": 0.85,
    "RedboxGlobal": 0.75,
}

TARGET_ACCOUNTS = list(ACCOUNT_WEIGHTS.keys())
DEFAULT_TWEETS_PER_ACCOUNT = 50
TWSCRAPE_DB = "data/twscrape.db"


def _weight_for(author: str) -> float:
    for handle, weight in ACCOUNT_WEIGHTS.items():
        if handle.lower() == author.lower():
            return weight
    return 0.70


async def _scrape_account(api, account: str, limit: int) -> List[dict]:
    from twscrape import gather

    tweets = []
    try:
        results = await gather(api.search(f"from:{account}", limit=limit))
        for tweet in results:
            ts = tweet.date.isoformat() if tweet.date else datetime.now(timezone.utc).isoformat()
            tweets.append({
                "id": str(tweet.id),
                "text": tweet.rawContent or "",
                "author": account,
                "timestamp": ts,
                "account_weight": _weight_for(account),
            })
    except Exception as e:
        print(f"[SCRAPER] {account}: {e}")
    return tweets


async def _fetch_all() -> List[dict]:
    from twscrape import API

    os.makedirs("data", exist_ok=True)
    api = API(TWSCRAPE_DB)

    accounts_env = os.getenv("TWITTER_ACCOUNTS", "")
    if accounts_env:
        for entry in accounts_env.split(";"):
            parts = [p.strip() for p in entry.split(",")]
            if len(parts) >= 4:
                await api.pool.add_account(parts[0], parts[1], parts[2], parts[3])
        await api.pool.login_all()

    limit = int(os.getenv("TWEETS_PER_ACCOUNT", str(DEFAULT_TWEETS_PER_ACCOUNT)))
    tasks = [_scrape_account(api, acct, limit) for acct in TARGET_ACCOUNTS]
    results = await asyncio.gather(*tasks)

    all_tweets: List[dict] = []
    for batch in results:
        all_tweets.extend(batch)
    return all_tweets


def fetch_tweets() -> List[dict]:
    """Fetch tweets from all target accounts. Returns [] if scraper is not configured."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_fetch_all())
    except ImportError:
        print("[SCRAPER] twscrape not installed. Run: pip install twscrape")
        return []
    except Exception as e:
        print(f"[SCRAPER] Critical failure: {e}")
        return []
    finally:
        try:
            loop.close()
        except Exception:
            pass
