def report_node(state):
    status = state.get("status")
    if not status or status == "PENDING":
        status = "SUCCESS"

    signal = state.get("signal") or state.get("recommendation") or "NEUTRAL"
    analysis = state.get("analysis") or state.get("recommendation_reason") or ""

    state["report"] = f"""
SYMBOL: {state['symbol']}
STATUS: {status}
SIGNAL: {signal}
CONFIDENCE: {state.get('confidence') or 'Low'}
ALREADY_REFLECTED: {state.get('already_reflected', False)}
NOTIFY: {state.get('notify', False)}
PDF_SUMMARY_CHARS: {len(state.get('pdf_summary', ''))}

{analysis}
""".strip()

    state["status"] = status
    return state
