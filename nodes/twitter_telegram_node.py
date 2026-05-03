import json
from datetime import datetime, timezone
from pathlib import Path

from services.telegram_service import send_telegram_message
from utils.logger import log

_PER_MESSAGE = 5    # summaries bundled into one Telegram message
_MAX_MESSAGES = 4   # cap outbound messages per run (≤ 20 summaries reach Telegram)
_OUTPUT_FILE = Path("data/twitter_output.json")
_MAX_STORED_RUNS = 500


# ── Telegram formatting ───────────────────────────────────────────────────────

def _format_digest(summaries: list, run_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    lines = [f"📰 Market Updates  |  {ts}  |  run {run_id}", ""]

    for item in summaries:
        stocks = ", ".join(item.get("stock_tags", [])) or "—"
        author = item.get("author", "?")
        lines.append(f"• [{author}]  {stocks}")
        lines.append(f"  {item.get('summary', '')}")

    return "\n".join(lines)


# ── Output persistence ────────────────────────────────────────────────────────

def _save_run(state: dict, alerts_sent: int, errors: list) -> None:
    record = {
        "run_id": state.get("run_id", "?"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline_stats": {
            "raw_tweets": len(state.get("raw_tweets", [])),
            "filtered_tweets": len(state.get("filtered_tweets", [])),
            "deduplicated_tweets": len(state.get("deduplicated_tweets", [])),
            "summaries": len(state.get("summaries", [])),
            "alerts_sent": alerts_sent,
        },
        "summaries": state.get("summaries", []),
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
        log("OUTPUT", f"Saved to {_OUTPUT_FILE}  ({len(state.get('summaries', []))} summaries)")
    except Exception as e:
        log("OUTPUT", f"Save failed: {e}")


# ── Node ──────────────────────────────────────────────────────────────────────

def twitter_telegram_node(state: dict) -> dict:
    summaries = state.get("summaries", [])
    run_id = state.get("run_id", "?")
    sent = 0
    errors = []

    if not summaries:
        log("TELEGRAM", "No summaries to send")
        state["alerts_sent"] = 0
        state["telegram_errors"] = []
        _save_run(state, 0, [])
        return state

    for chunk_start in range(0, len(summaries), _PER_MESSAGE):
        if sent >= _MAX_MESSAGES:
            log("TELEGRAM", f"Reached message cap ({_MAX_MESSAGES}), stopping")
            break

        chunk = summaries[chunk_start: chunk_start + _PER_MESSAGE]
        message = _format_digest(chunk, run_id)

        try:
            send_telegram_message(message)
            sent += 1
            log("TELEGRAM", f"Sent digest {sent} ({len(chunk)} updates)")
        except Exception as e:
            errors.append(str(e))
            log("TELEGRAM", f"Failed digest {sent + 1}: {e}")

    state["alerts_sent"] = sent
    state["telegram_errors"] = errors

    _save_run(state, sent, errors)
    return state
