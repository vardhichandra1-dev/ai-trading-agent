"""
run.py — single entry point for the combined NSE + Twitter agent.

Starts one combined LangGraph cycle per iteration.
Each cycle:
  1. Refreshes NSE master data.
  2. Runs the NSE announcement pipeline AND Twitter summarisation pipeline IN PARALLEL.
  3. Both pipelines send their results to Telegram independently.

Sleep logic:
  - NSE found a pending record  → loop again immediately (drain the queue).
  - NSE queue empty / failed    → sleep 2–5 min, then start the next cycle.

Usage:
    python run.py           # continuous loop
    python run.py --once    # single cycle then exit
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from combined_graph import build_combined_graph

load_dotenv()

_MIN_SLEEP = 2 * 60   # 2 minutes
_MAX_SLEEP = 5 * 60   # 5 minutes
_COMBINED_LOG = Path("data/combined_runs.json")
_MAX_STORED_RUNS = 500


# ── Output persistence ───────────────────────────────────────────────────────

def _save_combined_run(result: dict) -> None:
    record = {
        "run_id": result.get("run_id", "?"),
        "timestamp": datetime.now().isoformat(),
        "nse": {
            "status": result.get("nse_status", ""),
            "symbol": result.get("nse_symbol", ""),
            "signal": result.get("nse_signal", ""),
            "telegram_sent": result.get("nse_telegram_sent", False),
            "error": result.get("nse_error", ""),
        },
        "twitter": {
            "status": result.get("twitter_status", ""),
            "summaries_count": result.get("twitter_summaries_count", 0),
            "alerts_sent": result.get("twitter_alerts_sent", 0),
            "error": result.get("twitter_error", ""),
        },
    }
    try:
        _COMBINED_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing: list = []
        if _COMBINED_LOG.exists() and _COMBINED_LOG.stat().st_size > 0:
            try:
                existing = json.loads(_COMBINED_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        runs = [record] + existing
        _COMBINED_LOG.write_text(
            json.dumps(runs[:_MAX_STORED_RUNS], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[OUTPUT] combined_runs.json save failed: {e}")


# ── State helpers ─────────────────────────────────────────────────────────────

def _blank_state() -> dict:
    return {
        "run_id": str(uuid.uuid4())[:8],
        "nse_status": "",
        "nse_symbol": "",
        "nse_signal": "",
        "nse_telegram_sent": False,
        "nse_error": "",
        "twitter_status": "",
        "twitter_summaries_count": 0,
        "twitter_alerts_sent": 0,
        "twitter_error": "",
    }


# ── Console output ────────────────────────────────────────────────────────────

def _hr(char: str = "─", width: int = 64) -> str:
    return char * width


def _print_summary(result: dict) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(_hr("═"))
    print(f"  Run {result.get('run_id')}   {ts}")
    print(_hr())

    # NSE
    nse_ok = result.get("nse_status") not in ("", "NO_PENDING", "FAILED")
    print("  NSE Announcements Pipeline")
    print(f"    Status  : {result.get('nse_status') or '—'}")
    if nse_ok:
        print(f"    Stock   : {result.get('nse_symbol') or '—'}")
        print(f"    Signal  : {result.get('nse_signal') or '—'}")
        print(f"    Telegram: {'✓ sent' if result.get('nse_telegram_sent') else '— skipped'}")
    if result.get("nse_error"):
        print(f"    Error   : {result['nse_error'][:120]}")

    print(_hr())

    # Twitter
    print("  Twitter Summarisation Pipeline")
    print(f"    Status    : {result.get('twitter_status') or '—'}")
    print(f"    Summaries : {result.get('twitter_summaries_count', 0)}")
    print(f"    Telegram  : {result.get('twitter_alerts_sent', 0)} message(s) sent")
    if result.get("twitter_error"):
        print(f"    Error     : {result['twitter_error'][:120]}")

    print(_hr("═"))
    print()


# ── Run cycle ─────────────────────────────────────────────────────────────────

def run_cycle(graph) -> dict:
    state = _blank_state()
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ts}] ── Starting cycle {state['run_id']} ──────────────────────────────")
    try:
        result = graph.invoke(state)
    except Exception as e:
        print(f"[ERROR] Combined graph failed: {e}")
        state["nse_status"] = "FAILED"
        state["nse_error"] = str(e)
        state["twitter_status"] = "FAILED"
        state["twitter_error"] = str(e)
        result = state
    _save_combined_run(result)
    return result


# ── Main loop ─────────────────────────────────────────────────────────────────

def main(once: bool = False) -> None:
    print("Building combined graph (NSE + Twitter)...")
    graph = build_combined_graph()
    print("Ready.\n")

    while True:
        result = run_cycle(graph)
        _print_summary(result)

        if once:
            break

        nse_status = result.get("nse_status", "")

        if nse_status not in ("NO_PENDING", "FAILED", ""):
            # A record was processed — check for more pending records immediately.
            # Twitter will also run again in the next parallel cycle.
            print("NSE record processed → checking for more pending records...")
            continue

        sleep_sec = random.randint(_MIN_SLEEP, _MAX_SLEEP)
        m, s = divmod(sleep_sec, 60)
        print(f"Queue empty — sleeping {m}:{s:02d} before next cycle.  Ctrl-C to stop.")
        time.sleep(sleep_sec)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Combined NSE announcements + Twitter stock news agent."
    )
    p.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        main(once=args.once)
    except KeyboardInterrupt:
        print("\nStopped.")
