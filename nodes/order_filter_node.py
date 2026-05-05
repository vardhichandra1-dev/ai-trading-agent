from services.order_filter_service import filter_order
from utils.logger import log


def order_filter_node(state: dict) -> dict:
    record = (state.get("records") or [{}])[0]
    result = filter_order(record)

    state["order_filter"] = result

    symbol = result["stock"]
    status = result["status"]
    score = result["score"]
    reason = result["reason"]

    log("ORDER_FILTER", f"{symbol} → {status} | {reason}")

    if status == "REJECT":
        state["signal"] = "FILTERED"
        state["confidence"] = "N/A"
        state["notify"] = False
        state["recommendation"] = "FILTERED"
        state["recommendation_reason"] = (
            f"Pre-filter rejected this announcement (score={score}): {reason}"
        )
        state["status"] = "FILTERED"

    return state
