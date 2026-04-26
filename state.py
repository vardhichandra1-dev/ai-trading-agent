# state.py

from typing import TypedDict, List, Dict


class GraphState(TypedDict):
    symbol: str
    records: List[Dict]

    pdf_text: str
    queries: List[str]
    search_results: str

    market_data: Dict
    market_skipped: bool

    analysis: str
    report: str
    recommendation: str
    recommendation_reason: str

    status: str
    error_stage: str
    error_reason: str
