def report_node(state):
    status = state.get("status")
    if not status or status == "PENDING":
        status = "SUCCESS"

    state["report"] = f"""
SYMBOL: {state['symbol']}
STATUS: {status}
SIGNAL: {state.get('signal') or state.get('recommendation') or 'NEUTRAL'}
CONFIDENCE: {state.get('confidence') or 'Low'}

{state['analysis']}
""".strip()

    state["status"] = status
    return state
