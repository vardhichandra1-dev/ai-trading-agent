import re
from utils.logger import log

_URL_RE = re.compile(r"https?://\S+")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F]+",
    flags=re.UNICODE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = _URL_RE.sub("", text)
    text = _EMOJI_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def noise_filter_node(state: dict) -> dict:
    raw = state.get("raw_tweets", [])
    filtered = [
        {
            "tweet_id": t["tweet_id"],
            "raw_text": t["raw_text"],
            "clean_text": _clean(t.get("raw_text", "")),
            "author": t.get("author", ""),
            "created_at": t["created_at"],
            "source": t.get("source", ""),
        }
        for t in raw
        if t.get("raw_text", "").strip()
    ]
    state["filtered_tweets"] = filtered
    log("FILTER", f"{len(raw)} raw → {len(filtered)} kept")
    return state
