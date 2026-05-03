from services.stock_detector_service import detect_stocks
from utils.logger import log


def stock_detector_node(state: dict) -> dict:
    """Tag each tweet with detected NSE symbols. No grouping or signal logic."""
    tweets = state.get("deduplicated_tweets", [])
    tagged = []

    for tweet in tweets:
        stock_tags = detect_stocks(tweet["clean_text"])
        tagged.append({**tweet, "stock_tags": stock_tags})

    state["deduplicated_tweets"] = tagged

    stocks_found = {s for t in tagged for s in t["stock_tags"]}
    log("DETECTOR", f"Tagged {len(tagged)} tweets; {len(stocks_found)} unique stocks: {', '.join(sorted(stocks_found)) or 'none'}")
    return state
