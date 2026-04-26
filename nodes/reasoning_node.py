from services.ollama_service import call_reasoning_model

VALID_RECOMMENDATIONS = {"BUY", "SELL", "NEUTRAL"}


def extract_recommendation(analysis):
    for line in analysis.splitlines():
        clean = line.strip().upper().replace("*", "")
        if clean.startswith("RECOMMENDATION:"):
            value = clean.split(":", 1)[1].strip()
            value = value.split()[0].strip(" .:-")
            if value in VALID_RECOMMENDATIONS:
                return value

    upper = analysis.upper()
    if "RECOMMENDATION: BUY" in upper or " BUY " in upper:
        return "BUY"
    if "RECOMMENDATION: SELL" in upper or " SELL " in upper:
        return "SELL"
    if "NEUTRAL" in upper or "SIDEWAYS" in upper or "RANGE-BOUND" in upper:
        return "NEUTRAL"

    return "NEUTRAL"


def extract_recommendation_reason(analysis):
    for line in analysis.splitlines():
        clean = line.strip().strip("*")
        if clean.upper().startswith("RECOMMENDATION_REASON:"):
            return clean.split(":", 1)[1].strip()
    return "See analysis for supporting reasoning."


def reasoning_node(state):
    prompt = f"""
You are a senior Indian stock-market research analyst.

Analyze this NSE corporate announcement for a short-term trader.

NSE announcement:
{state['records']}

PDF disclosure text:
{state.get('pdf_text', '')[:1500]}

External search context:
{state.get('search_results', '')[:1500]}

Live market data:
{state.get('market_data', {})}

Was live market data skipped:
{state.get('market_skipped')}

Start your answer with exactly these two lines:
RECOMMENDATION: BUY or SELL or NEUTRAL
RECOMMENDATION_REASON: one sentence explaining the main reason

Decision rules:
- BUY means the announcement and market context suggest positive short-term risk/reward.
- SELL means the announcement and market context suggest negative short-term risk/reward.
- NEUTRAL means the event is routine, already priced in, unclear, or risk/reward is balanced.

Reasoning requirements:
- Identify the event type and whether it is material or routine.
- Compare with similar historical cases when the search context supports it.
- Evaluate whether the market appears to have already reacted when market data is available.
- Predict the likely next-session direction and confidence.
- Be conservative when evidence is incomplete.

Provide detailed reasoning after the first two required lines.
"""

    try:
        state["analysis"] = call_reasoning_model(prompt)
        state["recommendation"] = extract_recommendation(state["analysis"])
        state["recommendation_reason"] = extract_recommendation_reason(state["analysis"])
    except Exception as e:
        state["analysis"] = f"LLM analysis failed: {e}"
        state["recommendation"] = "NEUTRAL"
        state["recommendation_reason"] = "LLM analysis failed, so no actionable trade decision was generated."
        state["status"] = "FAILED"
        state["error_stage"] = "REASONING"
        state["error_reason"] = str(e)
    return state
