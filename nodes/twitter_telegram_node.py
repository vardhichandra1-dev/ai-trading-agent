from datetime import datetime, timezone

from services.telegram_service import send_telegram_message
from utils.logger import log

_PER_MESSAGE = 5   # summaries bundled into one Telegram message
_MAX_MESSAGES = 4  # cap outbound messages per run (≤ 20 summaries reach Telegram)


def _format_digest(summaries: list, run_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    lines = [f"📰 Market Updates  |  {ts}  |  run {run_id}", ""]

    for item in summaries:
        stocks = ", ".join(item.get("stock_tags", [])) or "—"
        author = item.get("author", "?")
        summary = item.get("summary", "")
        lines.append(f"• [{author}]  {stocks}")
        lines.append(f"  {summary}")

    return "\n".join(lines)


def twitter_telegram_node(state: dict) -> dict:
    summaries = state.get("summaries", [])
    run_id = state.get("run_id", "?")
    sent = 0
    errors = []

    if not summaries:
        log("TELEGRAM", "No summaries to send")
        state["alerts_sent"] = 0
        state["telegram_errors"] = []
        return state

    # Chunk summaries into digest messages
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
    return state
