import json
from datetime import datetime, timezone
from pathlib import Path

from services.telegram_service import send_telegram_message
from utils.logger import log

_PER_MESSAGE = 5
_MAX_MESSAGES = 4
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
        ids = list(seen)[-_MAX_SEEN_IDS:]
        _SEEN_IDS_FILE.write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log("SEEN_IDS", f"Save failed: {e}")


# ── Telegram formatting ───────────────────────────────────────────────────────

def _format_digest(summaries: list, run_id: str, msg_num: int, total_new: int) -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%H:%M UTC")

    lines = [
        f"📊 *Market Flash*  ·  {date_str}  ·  {time_str}",
        "",
    ]

    for i, item in enumerate(summaries, start=1 + (msg_num - 1) * _PER_MESSAGE):
        summary = item.get("summary", "").strip()
        if not summary or summary in ("No market update.", "Summary unavailable."):
            continue

        author = item.get("author", "")
        stocks = item.get("stock_tags", [])

        lines.append(f"*{i}.* {summary}")

        meta_parts = []
        if stocks:
            meta_parts.append("🏷 " + "  ".join(stocks))
        meta_parts.append(f"@{author}")
        lines.append("    " + "  ·  ".join(meta_parts))
        lines.append("")

    lines.append(f"─────────────────────────")
    lines.append(f"🔄 {total_new} new update{'s' if total_new != 1 else ''}  ·  `{run_id}`")

    return "\n".join(lines)


# ── Output persistence ────────────────────────────────────────────────────────

def _build_tweet_records(state: dict) -> list:
    return [
        {
            "tweet_id": t.get("tweet_id", ""),
            "author": t.get("author", ""),
            "raw_text": t.get("raw_text", ""),
            "clean_text": t.get("clean_text", ""),
            "summary": t.get("summary", ""),
            "created_at": t.get("created_at", ""),
            "stock_tags": t.get("stock_tags", []),
            "source": t.get("source", ""),
        }
        for t in state.get("deduplicated_tweets", [])
    ]


def _save_run(state: dict, alerts_sent: int, errors: list, new_count: int) -> None:
    record = {
        "run_id": state.get("run_id", "?"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_stats": {
            "raw_tweets": len(state.get("raw_tweets", [])),
            "filtered_tweets": len(state.get("filtered_tweets", [])),
            "deduplicated_tweets": len(state.get("deduplicated_tweets", [])),
            "new_tweets": new_count,
            "summaries": len(state.get("summaries", [])),
            "alerts_sent": alerts_sent,
        },
        "tweets": _build_tweet_records(state),
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
        log("OUTPUT", f"Saved {len(_build_tweet_records(state))} tweet records  ({new_count} new)")
    except Exception as e:
        log("OUTPUT", f"Save failed: {e}")


# ── Node ──────────────────────────────────────────────────────────────────────

def twitter_telegram_node(state: dict) -> dict:
    all_summaries = state.get("summaries", [])
    run_id = state.get("run_id", "?")

    # Filter to only tweets not previously sent
    seen_ids = _load_seen_ids()
    new_summaries = [s for s in all_summaries if s.get("tweet_id") not in seen_ids]
    # Drop "No market update" entries before sending
    sendable = [s for s in new_summaries if s.get("summary", "").strip()
                not in ("", "No market update.", "Summary unavailable.")]

    log("TELEGRAM", f"{len(all_summaries)} summaries total — {len(sendable)} new to send")

    sent = 0
    errors = []

    if not sendable:
        state["alerts_sent"] = 0
        state["telegram_errors"] = []
        _save_run(state, 0, [], 0)
        return state

    for chunk_start in range(0, len(sendable), _PER_MESSAGE):
        if sent >= _MAX_MESSAGES:
            log("TELEGRAM", f"Reached message cap ({_MAX_MESSAGES}), stopping")
            break

        chunk = sendable[chunk_start: chunk_start + _PER_MESSAGE]
        message = _format_digest(chunk, run_id, sent + 1, len(sendable))

        try:
            send_telegram_message(message)
            sent += 1
            # Mark these IDs as seen only after successful send
            for item in chunk:
                seen_ids.add(item.get("tweet_id", ""))
            log("TELEGRAM", f"Sent digest {sent} ({len(chunk)} updates)")
        except Exception as e:
            errors.append(str(e))
            log("TELEGRAM", f"Failed digest {sent + 1}: {e}")

    _save_seen_ids(seen_ids)
    state["alerts_sent"] = sent
    state["telegram_errors"] = errors
    _save_run(state, sent, errors, len(sendable))
    return state
