from typing import TypedDict, List, Dict


class TwitterState(TypedDict):
    run_id: str
    raw_tweets: List[Dict]
    filtered_tweets: List[Dict]
    deduplicated_tweets: List[Dict]
    summaries: List[Dict]
    fetch_debug: List[Dict]
    alerts_sent: int
    telegram_errors: List[str]
    status: str
    error_stage: str
    error_reason: str
