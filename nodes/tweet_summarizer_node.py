import json
import re
from typing import List

from services.llm_service import call_llm
from utils.logger import log

_BATCH_SIZE = 10

_PROMPT = """\
You are a financial news assistant covering Indian stock markets.

Summarize each tweet below in ONE concise sentence (max 25 words).
Extract only the key market fact. Ignore promotional language, hashtags, and filler text.
If a tweet contains no market-relevant fact, write "No market update."

Tweets:
{tweets}

Return ONLY a JSON array — no prose, no markdown:
[
  {{"index": 0, "summary": "concise one-sentence summary"}},
  {{"index": 1, "summary": "concise one-sentence summary"}}
]"""


def _parse(response: str, count: int) -> List[str]:
    """Extract summary strings from LLM JSON response, falling back gracefully."""
    try:
        raw = response.strip()
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        data = json.loads(m.group(0) if m else raw)
        result = [""] * count
        for item in data:
            idx = int(item.get("index", -1))
            if 0 <= idx < count:
                result[idx] = str(item.get("summary", "")).strip()
        return result
    except Exception:
        snippet = response.strip()[:120]
        return [snippet] * count


def tweet_summarizer_node(state: dict) -> dict:
    tweets = state.get("deduplicated_tweets", [])
    summaries = []

    for batch_start in range(0, len(tweets), _BATCH_SIZE):
        batch = tweets[batch_start: batch_start + _BATCH_SIZE]

        tweet_block = "\n".join(
            f"[{i}] [{t['author']}] {t['clean_text']}"
            for i, t in enumerate(batch)
        )
        prompt = _PROMPT.format(tweets=tweet_block)

        try:
            raw = call_llm(prompt, options={"temperature": 0.1, "max_tokens": 800})
            batch_summaries = _parse(raw, len(batch))
        except Exception as e:
            log("SUMMARIZER", f"Batch {batch_start // _BATCH_SIZE + 1} failed: {e}")
            batch_summaries = ["Summary unavailable."] * len(batch)

        for tweet, summary in zip(batch, batch_summaries):
            tweet["summary"] = summary if summary else "Summary unavailable."

            is_redbox = tweet.get("author", "").upper() == "REDBOXINDIA"
            has_summary = summary and summary != "No market update."

            if is_redbox or has_summary:
                summaries.append({
                    "author": tweet["author"],
                    "stock_tags": tweet.get("stock_tags", []),
                    "summary": summary,
                    # raw_text kept so Telegram can display it when summary is absent
                    "raw_text": tweet.get("raw_text", ""),
                    "clean_text": tweet.get("clean_text", ""),
                    "timestamp": tweet["created_at"],
                    "tweet_id": tweet["tweet_id"],
                })

    state["summaries"] = summaries
    log("SUMMARIZER", f"{len(tweets)} tweets → {len(summaries)} summaries")
    return state
