from services.twitter_scraper_service import fetch_tweets
from utils.logger import log


def tweet_collector_node(state: dict) -> dict:
    try:
        tweets, debug_logs = fetch_tweets()
        state["raw_tweets"] = tweets
        state["fetch_debug"] = debug_logs
        log("COLLECTOR", f"Fetched {len(tweets)} raw tweets from {len(debug_logs)} accounts")
    except Exception as e:
        state["raw_tweets"] = []
        state["fetch_debug"] = []
        state["status"] = "FAILED"
        state["error_stage"] = "COLLECTOR"
        state["error_reason"] = str(e)
        log("COLLECTOR", f"Failed: {e}")
    return state
