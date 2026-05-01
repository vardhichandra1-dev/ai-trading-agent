import json
import os
import requests
from datetime import datetime, timezone
from pathlib import Path

SEARCH_LOG_FILE = Path("data/tavily_search_log.json")


def _load_log():
    if SEARCH_LOG_FILE.exists() and SEARCH_LOG_FILE.stat().st_size > 0:
        try:
            with SEARCH_LOG_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return []


def save_search_log(symbol, signal, queries, results_by_query):
    """Document Tavily search session for a BUY/SELL signal stock in JSON format."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "signal": signal,
        "search_queries": [
            {
                "query": q,
                "results_count": len(results_by_query.get(q, [])),
            }
            for q in queries
        ],
        "total_results": sum(len(v) for v in results_by_query.values()),
    }
    SEARCH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = _load_log()
    log.insert(0, entry)
    with SEARCH_LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def search_tavily(query):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY is not set")

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": 3,
    }

    res = requests.post(url, json=payload, timeout=20)
    res.raise_for_status()
    return [r.get("content", "") for r in res.json().get("results", []) if r.get("content")]
