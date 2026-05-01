# state.py

from typing import TypedDict, List, Dict


class GraphState(TypedDict):
    symbol: str
    records: List[Dict]

    pdf_text: str
    pdf_summary: str
    queries: List[str]
    search_results: str

    analysis: str
    report: str
    signal: str
    confidence: str
    already_reflected: bool
    notify: bool
    recommendation: str
    recommendation_reason: str
    telegram_message: str
    telegram_sent: bool
    telegram_error: str

    status: str
    error_stage: str
    error_reason: str
