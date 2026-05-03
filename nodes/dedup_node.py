from services.dedup_service import deduplicate
from utils.logger import log


def dedup_node(state: dict) -> dict:
    tweets = state.get("filtered_tweets", [])
    deduped = deduplicate(tweets)
    state["deduplicated_tweets"] = deduped
    log("DEDUP", f"{len(tweets)} → {len(deduped)} after deduplication")
    return state
