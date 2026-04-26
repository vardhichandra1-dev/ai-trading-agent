from datetime import datetime, time
from services.kite_service import get_quote
from utils.logger import log
from utils.retry import retry

def is_market_open(dt):
    market_start = time(9, 15)
    market_end = time(15, 30)
    return market_start <= dt.time() <= market_end

def market_node(state):
    try:
        raw_dt = state["records"][0].get("BROADCAST DATE/TIME")
        if not raw_dt:
            state["market_skipped"] = True
            state["error_stage"] = state.get("error_stage") or "MARKET"
            state["error_reason"] = state.get("error_reason") or "Missing broadcast date/time"
            return state

        dt = datetime.fromisoformat(raw_dt)

        if not is_market_open(dt):
            log("MARKET", "Skipped")
            state["market_skipped"] = True
            return state

        data = retry(lambda: get_quote(state["symbol"]))

        state["market_data"] = data
        state["market_skipped"] = False

        return state

    except Exception as e:
        state["market_skipped"] = True
        state["error_stage"] = "MARKET"
        state["error_reason"] = str(e)
        return state
