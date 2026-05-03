from typing import TypedDict, List, Dict


class TwitterState(TypedDict):
    run_id: str
    raw_tweets: List[Dict]
    filtered_tweets: List[Dict]
    # each tweet has stock_tags: List[str] added by stock_detector_node
    deduplicated_tweets: List[Dict]
    # one dict per tweet: {author, stock_tags, summary, timestamp}
    summaries: List[Dict]
    alerts_sent: int
    telegram_errors: List[str]
    status: str
    error_stage: str
    error_reason: str
