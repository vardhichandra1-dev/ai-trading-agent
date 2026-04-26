def report_node(state):
    status = state.get("status")
    if not status or status == "PENDING":
        status = "SUCCESS"

    state["report"] = f"""
STOCK: {state['symbol']}
STATUS: {status}
RECOMMENDATION: {state.get('recommendation') or 'NEUTRAL'}
RECOMMENDATION_REASON: {state.get('recommendation_reason') or 'See analysis for supporting reasoning.'}

{state['analysis']}
""".strip()

    state["status"] = status
    return state
