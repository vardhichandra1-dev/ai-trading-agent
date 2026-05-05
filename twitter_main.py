import argparse
import random
import time
import uuid
from datetime import datetime

from dotenv import load_dotenv

from twitter_graph import build_twitter_graph

load_dotenv()

MIN_SLEEP = 2 * 60   # 2 minutes
MAX_SLEEP = 5 * 60   # 5 minutes


def _initial_state() -> dict:
    return {
        "run_id": str(uuid.uuid4())[:8],
        "raw_tweets": [],
        "filtered_tweets": [],
        "deduplicated_tweets": [],
        "summaries": [],
        "fetch_debug": [],
        "alerts_sent": 0,
        "telegram_errors": [],
        "status": "PENDING",
        "error_stage": "",
        "error_reason": "",
    }


def _print_summary(state: dict) -> None:
    summaries = state.get("summaries", [])
    print()
    print("=" * 64)
    print(f"Run: {state.get('run_id')}  |  {datetime.now().strftime('%H:%M:%S')}")
    print(f"  Raw tweets    : {len(state.get('raw_tweets', []))}")
    print(f"  After filter  : {len(state.get('filtered_tweets', []))}")
    print(f"  After dedup   : {len(state.get('deduplicated_tweets', []))}")
    print(f"  Summaries     : {len(summaries)}")
    print(f"  Telegram sent : {state.get('alerts_sent', 0)} message(s)")
    if summaries:
        print()
        print("  Latest updates:")
        for s in summaries[:5]:
            stocks = ", ".join(s.get("stock_tags", [])) or "—"
            print(f"    [{s['author']}] {stocks}")
            print(f"      {s['summary']}")
    if state.get("telegram_errors"):
        print()
        print(f"  Telegram errors: {state['telegram_errors']}")
    print("=" * 64)
    print()


def run_once(graph) -> dict:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Twitter summarisation run...")
    state = _initial_state()
    try:
        result = graph.invoke(state)
    except Exception as e:
        print(f"Pipeline error: {e}")
        state["status"] = "FAILED"
        state["error_reason"] = str(e)
        result = state
    _print_summary(result)
    return result


def main(once: bool = False) -> None:
    graph = build_twitter_graph()

    while True:
        run_once(graph)

        if once:
            break

        sleep_sec = random.randint(MIN_SLEEP, MAX_SLEEP)
        print(f"Waiting {sleep_sec // 60}:{sleep_sec % 60:02d} before next run. Ctrl-C to stop.")
        time.sleep(sleep_sec)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Twitter stock news summarisation agent.")
    p.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    try:
        main(once=args.once)
    except KeyboardInterrupt:
        print("\nStopped.")
