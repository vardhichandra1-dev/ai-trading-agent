from services.tavily_service import search_tavily
from utils.retry import retry
from utils.logger import log

def search_node(state):
    results = []

    for q in state["queries"]:
        try:
            res = retry(lambda: search_tavily(q))
            results.extend(res)
        except Exception as e:
            state["error_stage"] = state.get("error_stage") or "SEARCH"
            state["error_reason"] = state.get("error_reason") or str(e)
            continue

    cleaned = " ".join(results[:10])

    log("SEARCH", f"{len(results)} results")

    state["search_results"] = cleaned
    return state
