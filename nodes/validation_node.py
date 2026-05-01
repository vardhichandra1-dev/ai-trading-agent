import json
import os
import re

from nodes.signal_node import extract_signal_payload
from services.llm_service import call_llm
from services.tavily_service import save_search_log, search_tavily
from utils.logger import log
from utils.retry import retry

MAX_INITIAL_REASONING_CHARS = 1800
MAX_PDF_VALIDATION_CHARS = 1200
MAX_SEARCH_CONTEXT_CHARS = 2500


def clean_query(query):
    return re.sub(r"\s+", " ", str(query)).strip(" -\"'")[:220]


def compact_text(text, max_chars):
    clean = " ".join(str(text or "").split())
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rstrip() + "..."


def parse_queries(response):
    text = response.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = parsed.get("queries", [])
        if isinstance(parsed, list):
            return [clean_query(q) for q in parsed if clean_query(q)]
    except json.JSONDecodeError:
        pass

    queries = []
    for line in text.splitlines():
        query = re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line)
        query = clean_query(query)
        if query:
            queries.append(query)
    return queries


def fallback_queries(record):
    company = record.get("COMPANY NAME") or record.get("SYMBOL", "")
    subject = record.get("SUBJECT") or "NSE announcement"
    return [
        f"{company} {subject} latest news",
        f"{company} {subject} announced earlier",
        f"{company} {subject} already priced in stock",
        f"{company} {subject} stock impact",
        f"{company} NSE announcement analysis",
    ]


def build_query_prompt(state):
    record = state["records"][0]
    signal = state.get("signal", "")
    return f"""
Generate 3 to 5 concise web search queries to validate this {signal} trading signal for an Indian stock.
The goal is to confirm whether this NSE event is fresh news not yet priced in, or was already public and reflected in the stock price.

For a {signal} signal, target queries that find:
- Recent news confirming or contradicting the {signal} rationale
- Whether the stock price has already reacted to this announcement
- Analyst views or institutional activity around this specific event

SYMBOL: {record.get("SYMBOL", "")}
COMPANY NAME: {record.get("COMPANY NAME", "")}
SUBJECT: {record.get("SUBJECT", "")}
DETAILS: {record.get("DETAILS", "")}
INITIAL SIGNAL: {signal}
INITIAL REASONING: {compact_text(state.get("analysis", ""), 900)}

Return only valid JSON:
["query 1", "query 2", "query 3"]
""".strip()


def build_validation_prompt(state):
    record = state["records"][0]
    initial_reasoning = compact_text(state.get("analysis", ""), MAX_INITIAL_REASONING_CHARS)
    pdf_excerpt = compact_text(state.get("pdf_summary") or state.get("pdf_text", ""), MAX_PDF_VALIDATION_CHARS)
    search_context = compact_text(state.get("search_results", ""), MAX_SEARCH_CONTEXT_CHARS)

    return f"""
You are validating an existing Indian stock trading signal using external search context.

Initial signal: {state.get("signal")}
Initial confidence: {state.get("confidence")}
Initial PDF-based reasoning:
{initial_reasoning}

NSE DATA:
SYMBOL: {record.get("SYMBOL", "")}
COMPANY NAME: {record.get("COMPANY NAME", "")}
SUBJECT: {record.get("SUBJECT", "")}
DETAILS: {record.get("DETAILS", "")}
BROADCAST DATE/TIME: {record.get("BROADCAST DATE/TIME", "")}
ATTACHMENT: {record.get("ATTACHMENT", "")}

Groq PDF summary or short PDF excerpt for reference:
{pdf_excerpt}

EXTERNAL SEARCH CONTEXT:
{search_context}

Confirm or refine the signal into exactly one of BUY, SELL, or NEUTRAL.
Use search only as validation. NSE data and PDF content remain the primary evidence.

Freshness rule:
- If the same material update was already reported publicly before this NSE announcement, or search context shows the market already reacted to it, set already_reflected=true, notify=false, and usually downgrade to NEUTRAL.
- If the event appears fresh and still actionable, set already_reflected=false and notify=true for BUY/SELL.
- NEUTRAL must always have notify=false.

Return only valid JSON:
{{
  "signal": "BUY or SELL or NEUTRAL",
  "confidence": "High or Medium or Low",
  "already_reflected": true or false,
  "notify": true or false,
  "reasoning": "Detailed reasoning including NSE event, PDF insights, external confirmation, and whether the update already appeared in the market earlier."
}}
""".strip()


def validation_node(state):
    if state.get("signal") not in {"BUY", "SELL"}:
        log("TAVILY", "Skipped for NEUTRAL signal")
        state["search_results"] = ""
        state["already_reflected"] = False
        state["notify"] = False
        return state

    record = state["records"][0]

    try:
        query_response = call_llm(
            build_query_prompt(state),
            timeout=int(os.getenv("GROQ_QUERY_TIMEOUT_SECONDS", "120")),
            options={"temperature": 0.2, "num_predict": 160},
        )
        queries = parse_queries(query_response)
    except Exception as e:
        queries = []
        state["error_stage"] = state.get("error_stage") or "QUERY"
        state["error_reason"] = state.get("error_reason") or str(e)

    if len(queries) < 3:
        queries.extend(fallback_queries(record))

    deduped = []
    seen = set()
    for query in queries:
        key = query.lower()
        if key not in seen:
            deduped.append(query)
            seen.add(key)

    state["queries"] = deduped[:5]
    log("QUERY", f"{len(state['queries'])} validation queries generated")

    results = []
    results_by_query = {}
    for query in state["queries"]:
        try:
            qresults = retry(lambda q=query: search_tavily(q))
            results_by_query[query] = qresults
            results.extend(qresults)
        except Exception as e:
            results_by_query[query] = []
            state["error_stage"] = state.get("error_stage") or "SEARCH"
            state["error_reason"] = state.get("error_reason") or str(e)

    try:
        save_search_log(
            symbol=record.get("SYMBOL", ""),
            signal=state.get("signal", ""),
            queries=state["queries"],
            results_by_query=results_by_query,
        )
    except Exception:
        pass

    state["search_results"] = compact_text(" ".join(results), MAX_SEARCH_CONTEXT_CHARS)
    log("TAVILY", f"{len(results)} results")

    if not results:
        state["notify"] = False
        state["already_reflected"] = False
        state["analysis"] = (
            f"{state.get('analysis', '')}\n\n"
            "Tavily validation returned no usable results, so no Telegram alert was sent."
        ).strip()
        state["recommendation_reason"] = state["analysis"]
        log("VALIDATION", "Skipped notification because Tavily returned no results")
        return state

    try:
        response = call_llm(
            build_validation_prompt(state),
            timeout=int(os.getenv("GROQ_VALIDATION_TIMEOUT_SECONDS", "240")),
            options={"temperature": 0.1, "num_predict": 384},
        )
        payload = extract_signal_payload(response)

        state["signal"] = payload["signal"]
        state["confidence"] = payload["confidence"]
        state["already_reflected"] = payload.get("already_reflected", False)
        state["notify"] = (
            payload.get("notify", state["signal"] in {"BUY", "SELL"})
            and state["signal"] in {"BUY", "SELL"}
            and not state["already_reflected"]
        )
        state["analysis"] = payload["reasoning"]
        state["recommendation"] = payload["signal"]
        state["recommendation_reason"] = payload["reasoning"]
        log(
            "VALIDATION",
            f"{state['signal']} / {state['confidence']} / notify={state['notify']} / already_reflected={state['already_reflected']}",
        )
    except Exception as e:
        state["error_stage"] = state.get("error_stage") or "VALIDATION"
        state["error_reason"] = state.get("error_reason") or str(e)
        state["analysis"] = (
            f"{state.get('analysis', '')}\n\n"
            "External validation could not complete, so the initial LLM signal was retained."
        ).strip()
        state["recommendation_reason"] = state["analysis"]
        state["already_reflected"] = False
        state["notify"] = False

    return state
