from services.twitter_scraper_service import fetch_tweets
from utils.logger import log


def tweet_collector_node(state: dict) -> dict:
    try:
        tweets = fetch_tweets()
        state["raw_tweets"] = tweets
        log("COLLECTOR", f"Fetched {len(tweets)} raw tweets")
    except Exception as e:
        state["raw_tweets"] = []
        state["status"] = "FAILED"
        state["error_stage"] = "COLLECTOR"
        state["error_reason"] = str(e)
        log("COLLECTOR", f"Failed: {e}")
    return state
