from services.telegram_service import send_telegram_message
from utils.logger import log


def short_reason(text, max_chars=260):
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."


def build_telegram_message(state):
    signal = state.get("signal") or state.get("recommendation") or "NEUTRAL"
    limit = 420 if signal in {"BUY", "SELL"} else 220

    return "\n".join(
        [
            f"Stock: {state.get('symbol') or 'UNKNOWN'}",
            f"Signal: {signal}",
            f"Confidence: {state.get('confidence') or 'Low'}",
            f"Reason: {short_reason(state.get('analysis') or state.get('recommendation_reason'), limit)}",
        ]
    )


def telegram_node(state):
    message = build_telegram_message(state)
    state["telegram_message"] = message

    try:
        send_telegram_message(message)
        state["telegram_sent"] = True
        log("TELEGRAM", "Sent")
    except Exception as e:
        state["telegram_sent"] = False
        state["telegram_error"] = str(e)
        state["error_stage"] = state.get("error_stage") or "TELEGRAM"
        state["error_reason"] = state.get("error_reason") or str(e)
        log("TELEGRAM", f"Failed: {e}")

    return state
