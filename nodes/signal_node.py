import json
import re

from services.llm_service import call_llm
from utils.logger import log

VALID_SIGNALS = {"BUY", "SELL", "NEUTRAL"}
VALID_CONFIDENCE = {"High", "Medium", "Low"}


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
        }

    return {
        "signal": normalize_signal(data.get("signal")),
        "confidence": normalize_confidence(data.get("confidence")),
        "reasoning": str(data.get("reasoning") or "").strip() or "No reasoning returned by Phi-3.",
    }


def build_initial_signal_prompt(state):
    record = state["records"][0]
    return f"""
You are an Indian stock trading signal analyst. Use only the NSE announcement fields and the full PDF disclosure text below.

Classify the stock into exactly one signal: BUY, SELL, or NEUTRAL.
Base the decision primarily on whether the NSE event and PDF content are material for short-term price movement.

NSE DATA:
SYMBOL: {record.get("SYMBOL", "")}
COMPANY NAME: {record.get("COMPANY NAME", "")}
SUBJECT: {record.get("SUBJECT", "")}
DETAILS: {record.get("DETAILS", "")}
BROADCAST DATE/TIME: {record.get("BROADCAST DATE/TIME", "")}
ATTACHMENT: {record.get("ATTACHMENT", "")}

FULL PDF TEXT:
{state.get("pdf_text", "")}

Return only valid JSON:
{{
  "signal": "BUY or SELL or NEUTRAL",
  "confidence": "High or Medium or Low",
  "reasoning": "Detailed reasoning with NSE event interpretation and PDF insights."
}}
""".strip()


def signal_node(state):
    try:
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
