import json
import os
import re

from services.llm_service import call_llm
from utils.logger import log

VALID_SIGNALS = {"BUY", "SELL", "NEUTRAL"}
VALID_CONFIDENCE = {"High", "Medium", "Low"}
TRUTHY_VALUES = {"true", "yes", "y", "1"}
DEFAULT_SIGNAL_PDF_MAX_CHARS = 18000
PDF_HEAD_CHARS = 7000
PDF_TAIL_CHARS = 3000
PDF_SNIPPET_CHARS = 1200


def normalize_signal(value):
    signal = str(value or "").strip().upper()
    return signal if signal in VALID_SIGNALS else "NEUTRAL"


def normalize_confidence(value):
    confidence = str(value or "").strip().title()
    return confidence if confidence in VALID_CONFIDENCE else "Low"


def parse_json_object(text):
    raw = text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    raise ValueError("Phi-3 response did not contain valid JSON")


def extract_signal_payload(response):
    try:
        data = parse_json_object(response)
    except Exception:
        upper = response.upper()
        if "SIGNAL: BUY" in upper:
            signal = "BUY"
        elif "SIGNAL: SELL" in upper:
            signal = "SELL"
        else:
            signal = "NEUTRAL"
        return {
            "signal": signal,
            "confidence": "Low",
            "reasoning": response.strip() or "No reasoning returned by Phi-3.",
            "already_reflected": False,
            "notify": signal in {"BUY", "SELL"},
        }

    return {
        "signal": normalize_signal(data.get("signal")),
        "confidence": normalize_confidence(data.get("confidence")),
        "reasoning": str(data.get("reasoning") or "").strip() or "No reasoning returned by Phi-3.",
        "already_reflected": str(data.get("already_reflected", "false")).strip().lower() in TRUTHY_VALUES,
        "notify": str(data.get("notify", "true")).strip().lower() in TRUTHY_VALUES,
    }


def compact_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def find_keyword_snippets(text, keywords, max_total_chars):
    snippets = []
    clean_text = str(text or "")
    lower_text = clean_text.lower()

    for keyword in keywords:
        keyword = str(keyword or "").strip().lower()
        if len(keyword) < 4:
            continue

        pos = lower_text.find(keyword)
        if pos < 0:
            continue

        start = max(0, pos - PDF_SNIPPET_CHARS // 2)
        end = min(len(clean_text), pos + PDF_SNIPPET_CHARS // 2)
        snippet = compact_text(clean_text[start:end])
        if snippet and snippet not in snippets:
            snippets.append(snippet)

        if sum(len(item) for item in snippets) >= max_total_chars:
            break

    return snippets


def build_pdf_context(record, pdf_text):
    pdf_text = str(pdf_text or "")
    max_chars = int(os.getenv("SIGNAL_PDF_MAX_CHARS", str(DEFAULT_SIGNAL_PDF_MAX_CHARS)))

    if len(pdf_text) <= max_chars:
        return pdf_text

    keywords = [
        record.get("SYMBOL", ""),
        record.get("COMPANY NAME", ""),
        record.get("SUBJECT", ""),
        record.get("DETAILS", ""),
        "revenue",
        "order",
        "contract",
        "acquisition",
        "merger",
        "approval",
        "investment",
        "capex",
        "profit",
        "loss",
        "guidance",
        "litigation",
        "default",
        "resignation",
    ]

    snippet_budget = max(0, max_chars - PDF_HEAD_CHARS - PDF_TAIL_CHARS - 500)
    snippets = find_keyword_snippets(pdf_text, keywords, snippet_budget)

    parts = [
        "[PDF BEGINNING]",
        pdf_text[:PDF_HEAD_CHARS],
    ]

    if snippets:
        parts.extend(["[EVENT-RELEVANT PDF SNIPPETS]", "\n\n".join(snippets)])

    parts.extend(["[PDF ENDING]", pdf_text[-PDF_TAIL_CHARS:]])

    return "\n\n".join(parts)[:max_chars]


def build_initial_signal_prompt(state):
    record = state["records"][0]
    pdf_context = state.get("pdf_summary") or build_pdf_context(record, state.get("pdf_text", ""))

    return f"""
You are an Indian stock trading signal analyst. Use only the NSE announcement fields and the PDF disclosure context below.

Classify the stock into exactly one signal: BUY, SELL, or NEUTRAL.
Base the decision primarily on whether the NSE event and PDF content are material for short-term price movement.

NSE DATA:
SYMBOL: {record.get("SYMBOL", "")}
COMPANY NAME: {record.get("COMPANY NAME", "")}
SUBJECT: {record.get("SUBJECT", "")}
DETAILS: {record.get("DETAILS", "")}
BROADCAST DATE/TIME: {record.get("BROADCAST DATE/TIME", "")}
ATTACHMENT: {record.get("ATTACHMENT", "")}

PDF TEXT CONTEXT:
{pdf_context}

Return only valid JSON:
{{
  "signal": "BUY or SELL or NEUTRAL",
  "confidence": "High or Medium or Low",
  "reasoning": "Detailed reasoning with NSE event interpretation and PDF insights."
}}
""".strip()


def signal_node(state):
    try:
        pdf_text = state.get("pdf_text", "")
        pdf_summary = state.get("pdf_summary", "")
        if pdf_summary:
            log("SIGNAL", f"Using Phi-3 PDF summary {len(pdf_summary)}/{len(pdf_text)} chars")
        else:
            pdf_context = build_pdf_context(state["records"][0], pdf_text)
            if len(pdf_text) > len(pdf_context):
                log("SIGNAL", f"Using compact PDF context {len(pdf_context)}/{len(pdf_text)} chars")

        response = call_llm(
            build_initial_signal_prompt(state),
            options={"temperature": 0.1},
        )
        payload = extract_signal_payload(response)

        state["signal"] = payload["signal"]
        state["confidence"] = payload["confidence"]
        state["analysis"] = payload["reasoning"]
        state["recommendation"] = payload["signal"]
        state["recommendation_reason"] = payload["reasoning"]

        log("SIGNAL", f"{state['signal']} / {state['confidence']}")
    except Exception as e:
        state["signal"] = "NEUTRAL"
        state["confidence"] = "Low"
        state["analysis"] = f"LLM signal generation failed: {e}"
        state["recommendation"] = "NEUTRAL"
        state["recommendation_reason"] = "Groq primary and local fallback models failed, so no actionable trade signal was generated."
        state["status"] = "FAILED"
        state["error_stage"] = "SIGNAL"
        state["error_reason"] = str(e)

    return state
