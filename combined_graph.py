import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from combined_state import CombinedState
from graph import build_graph as _build_nse_graph
from nse_fetcher import init_session, update_nse_master
from twitter_graph import build_twitter_graph as _build_twitter_graph
from utils.logger import log

# ── Subgraphs compiled once at import time ────────────────────────────────────
_nse_graph = _build_nse_graph()
_twitter_graph = _build_twitter_graph()

_NSE_DATA = Path("data/nse_master.json")
_NSE_OUTPUT = Path("data/ai_research_output.json")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path, default):
    if not path.exists() or path.stat().st_size == 0:
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _record_key(r: dict) -> str:
    return "|".join(str(r.get(f) or "") for f in ("SYMBOL", "BROADCAST DATE/TIME", "ATTACHMENT"))


def _result_key(res: dict) -> str:
    records = res.get("records") or []
    return _record_key(records[0]) if records else ""


def _nse_initial_state(record: dict) -> dict:
    return {
        "symbol": record.get("SYMBOL", ""),
        "records": [record],
        "pdf_text": "",
        "pdf_summary": "",
        "queries": [],
        "search_results": "",
        "analysis": "",
        "report": "",
        "signal": "",
        "confidence": "",
        "already_reflected": False,
        "notify": False,
        "recommendation": "",
        "recommendation_reason": "",
        "telegram_message": "",
        "telegram_sent": False,
        "telegram_error": "",
        "status": "PENDING",
        "error_stage": "",
        "error_reason": "",
    }


def _twitter_initial_state(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "raw_tweets": [],
        "filtered_tweets": [],
        "deduplicated_tweets": [],
        "summaries": [],
        "alerts_sent": 0,
        "telegram_errors": [],
        "status": "PENDING",
        "error_stage": "",
        "error_reason": "",
    }


# ── Graph nodes ───────────────────────────────────────────────────────────────

def refresh_node(state: dict) -> dict:
    """Refresh NSE master data. Runs once per cycle before the parallel branches."""
    try:
        init_session()
        update_nse_master()
        log("REFRESH", "NSE master updated")
    except Exception as e:
        log("REFRESH", f"Failed (non-fatal): {e}")
    return {}


def nse_pipeline_node(state: dict) -> dict:
    """
    Run the full NSE LangGraph for the next pending announcement.
    Runs in parallel with twitter_pipeline_node.
    """
    records = _load_json(_NSE_DATA, [])
    existing = _load_json(_NSE_OUTPUT, [])
    processed = {_result_key(r) for r in existing if _result_key(r)}
    pending = [r for r in records if _record_key(r) not in processed]

    if not pending:
        log("NSE", "No pending announcements")
        return {
            "nse_status": "NO_PENDING",
            "nse_symbol": "",
            "nse_signal": "",
            "nse_telegram_sent": False,
            "nse_error": "",
        }

    record = pending[0]
    symbol = record.get("SYMBOL", "UNKNOWN")
    log("NSE", f"Processing {symbol}")

    try:
        result = _nse_graph.invoke(_nse_initial_state(record))
        _save_json(_NSE_OUTPUT, [result] + existing)
        return {
            "nse_status": result.get("status") or "SUCCESS",
            "nse_symbol": result.get("symbol") or symbol,
            "nse_signal": result.get("signal") or result.get("recommendation") or "NEUTRAL",
            "nse_telegram_sent": bool(result.get("telegram_sent")),
            "nse_error": result.get("error_reason") or "",
        }
    except Exception as e:
        log("NSE", f"Pipeline failed: {e}")
        return {
            "nse_status": "FAILED",
            "nse_symbol": symbol,
            "nse_signal": "NEUTRAL",
            "nse_telegram_sent": False,
            "nse_error": str(e),
        }


def twitter_pipeline_node(state: dict) -> dict:
    """
    Run the full Twitter summarisation LangGraph.
    Runs in parallel with nse_pipeline_node.
    """
    try:
        result = _twitter_graph.invoke(_twitter_initial_state(state.get("run_id", "?")))
        return {
            "twitter_status": result.get("status") or "SUCCESS",
            "twitter_summaries_count": len(result.get("summaries", [])),
            "twitter_alerts_sent": result.get("alerts_sent", 0),
            "twitter_error": result.get("error_reason") or "",
        }
    except Exception as e:
        log("TWITTER", f"Pipeline failed: {e}")
        return {
            "twitter_status": "FAILED",
            "twitter_summaries_count": 0,
            "twitter_alerts_sent": 0,
            "twitter_error": str(e),
        }


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_combined_graph():
    """
    Combined graph topology:

        START
          │
        refresh          ← updates nse_master.json
         / \\
       nse  twitter      ← run in PARALLEL (LangGraph threads both)
         \\ /
          END

    Both nse and twitter send independently to Telegram during their runs.
    """
    builder = StateGraph(CombinedState)

    builder.add_node("refresh", refresh_node)
    builder.add_node("nse", nse_pipeline_node)
    builder.add_node("twitter", twitter_pipeline_node)

    builder.add_edge(START, "refresh")
    # Fan-out: both pipeline nodes execute in parallel after refresh
    builder.add_edge("refresh", "nse")
    builder.add_edge("refresh", "twitter")
    builder.add_edge("nse", END)
    builder.add_edge("twitter", END)

    return builder.compile()
