def report_node(state):
    status = state.get("status")
    if not status or status == "PENDING":
        status = "SUCCESS"

    state["report"] = f"""
SYMBOL: {state['symbol']}
STATUS: {status}
SIGNAL: {state.get('signal') or state.get('recommendation') or 'NEUTRAL'}
CONFIDENCE: {state.get('confidence') or 'Low'}
ALREADY_REFLECTED: {state.get('already_reflected', False)}
NOTIFY: {state.get('notify', False)}
PDF_SUMMARY_CHARS: {len(state.get('pdf_summary', ''))}

{state['analysis']}
""".strip()

    state["status"] = status
    return state
