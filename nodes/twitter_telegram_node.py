import json
from datetime import datetime, timezone
from pathlib import Path

from services.telegram_service import send_telegram_message
from utils.logger import log

_OUTPUT_FILE = Path("data/twitter_output.json")
_SEEN_IDS_FILE = Path("data/seen_tweet_ids.json")
_MAX_STORED_RUNS = 500
_MAX_SEEN_IDS = 5_000


# ── Seen-ID persistence ───────────────────────────────────────────────────────

def _load_seen_ids() -> set:
    try:
        if _SEEN_IDS_FILE.exists() and _SEEN_IDS_FILE.stat().st_size > 0:
            return set(json.loads(_SEEN_IDS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return set()


def _save_seen_ids(seen: set) -> None:
    try:
        _SEEN_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SEEN_IDS_FILE.write_text(
            json.dumps(list(seen)[-_MAX_SEEN_IDS:], ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        log("SEEN_IDS", f"Save failed: {e}")


# ── Telegram formatting ───────────────────────────────────────────────────────

def _format_tweet(tweet: dict) -> str:
    text = tweet.get("raw_text", "").strip() or tweet.get("clean_text", "").strip() or "—"

    # Parse timestamp for display
    ts_raw = tweet.get("created_at", "")
    try:
        dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        time_str = dt.strftime("%H:%M UTC  ·  %d %b %Y")
    except Exception:
        time_str = datetime.now(timezone.utc).strftime("%H:%M UTC  ·  %d %b %Y")

    return f"🔴 *REDBOXINDIA*\n\n{text}\n\n🕐 {time_str}"


# ── Output persistence ────────────────────────────────────────────────────────

def _save_run(state: dict, alerts_sent: int, errors: list, new_count: int) -> None:
    tweets = state.get("deduplicated_tweets", [])
    record = {
        "run_id": state.get("run_id", "?"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_stats": {
            "raw_tweets": len(state.get("raw_tweets", [])),
            "filtered_tweets": len(state.get("filtered_tweets", [])),
            "deduplicated_tweets": len(tweets),
            "new_tweets": new_count,
            "alerts_sent": alerts_sent,
        },
        "tweets": [
            {
                "tweet_id": t.get("tweet_id", ""),
                "author": t.get("author", ""),
                "raw_text": t.get("raw_text", ""),
                "clean_text": t.get("clean_text", ""),
                "created_at": t.get("created_at", ""),
                "stock_tags": t.get("stock_tags", []),
                "source": t.get("source", ""),
            }
            for t in tweets
        ],
        "fetch_debug": state.get("fetch_debug", []),
        "telegram_errors": errors,
    }

    try:
        _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if _OUTPUT_FILE.exists() and _OUTPUT_FILE.stat().st_size > 0:
            try:
                existing = json.loads(_OUTPUT_FILE.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        runs = [record] + existing
        _OUTPUT_FILE.write_text(
            json.dumps(runs[:_MAX_STORED_RUNS], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        log("OUTPUT", f"Saved {len(tweets)} records  ({new_count} new)")
    except Exception as e:
        log("OUTPUT", f"Save failed: {e}")


# ── Node ──────────────────────────────────────────────────────────────────────

def twitter_telegram_node(state: dict) -> dict:
    all_tweets = state.get("deduplicated_tweets", [])

    # Cross-run dedup: drop tweets already sent in a previous run
    seen_ids = _load_seen_ids()
    new_tweets = [t for t in all_tweets if t.get("tweet_id") not in seen_ids]

    # Sort oldest → newest so Telegram feed reads as a timeline
    new_tweets.sort(key=lambda t: t.get("created_at", ""))

    log("TELEGRAM", f"{len(all_tweets)} total — {len(new_tweets)} new to send")

    sent = 0
    errors = []

    if not new_tweets:
        state["alerts_sent"] = 0
        state["telegram_errors"] = []
        _save_run(state, 0, [], 0)
        return state

    for tweet in new_tweets:
        message = _format_tweet(tweet)
        try:
            send_telegram_message(message)
            seen_ids.add(tweet.get("tweet_id", ""))
            sent += 1
            log("TELEGRAM", f"Sent tweet {sent}/{len(new_tweets)}: {tweet.get('raw_text', '')[:60]}")
        except Exception as e:
            errors.append(str(e))
            log("TELEGRAM", f"Failed tweet {sent + 1}: {e}")

    _save_seen_ids(seen_ids)
    state["alerts_sent"] = sent
    state["telegram_errors"] = errors
    _save_run(state, sent, errors, len(new_tweets))
    return state
