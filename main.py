import argparse
import json
import random
import time
from pathlib import Path

from dotenv import load_dotenv

from graph import build_graph
from nse_fetcher import init_session, update_nse_master

load_dotenv()

DATA_FILE = Path("data/nse_master.json")
OUTPUT_FILE = Path("data/ai_research_output.json")
MIN_SLEEP_SECONDS = 5 * 60
MAX_SLEEP_SECONDS = 10 * 60


def load_json_file(path, default):
    if not path.exists() or path.stat().st_size == 0:
        return default

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default


def save_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_records():
    return load_json_file(DATA_FILE, [])


def load_results():
    return load_json_file(OUTPUT_FILE, [])


def record_key(record):
    return "|".join(
        str(record.get(field) or "")
        for field in ("SYMBOL", "BROADCAST DATE/TIME", "ATTACHMENT")
    )


def result_key(result):
    records = result.get("records") or []
    if records:
        return record_key(records[0])
    return ""


def initial_state(record):
    return {
        "symbol": record.get("SYMBOL", ""),
        "records": [record],
        "pdf_text": "",
        "queries": [],
        "search_results": "",
        "analysis": "",
        "report": "",
        "signal": "",
        "confidence": "",
        "recommendation": "",
        "recommendation_reason": "",
        "telegram_message": "",
        "telegram_sent": False,
        "telegram_error": "",
        "status": "PENDING",
        "error_stage": "",
        "error_reason": "",
    }


def failed_state(record, error):
    symbol = record.get("SYMBOL", "")
    recommendation_reason = "Pipeline failed, so no actionable trade decision was generated."
    return {
        "symbol": symbol,
        "records": [record],
        "pdf_text": "",
        "queries": [],
        "search_results": "",
        "analysis": "",
        "report": (
            f"SYMBOL: {symbol}\n"
            "STATUS: FAILED\n"
            "SIGNAL: NEUTRAL\n"
            "CONFIDENCE: Low\n\n"
            f"Pipeline failed: {error}"
        ),
        "signal": "NEUTRAL",
        "confidence": "Low",
        "recommendation": "NEUTRAL",
        "recommendation_reason": recommendation_reason,
        "telegram_message": "",
        "telegram_sent": False,
        "telegram_error": "",
        "status": "FAILED",
        "error_stage": "PIPELINE",
        "error_reason": str(error),
    }


def pick_next_unprocessed_record(records, results):
    processed = {result_key(result) for result in results if result_key(result)}
    pending = [record for record in records if record_key(record) not in processed]
    return pending[0] if pending else None


def print_recommendation(result):
    symbol = result.get("symbol") or "UNKNOWN"
    status = result.get("status") or "UNKNOWN"
    signal = result.get("signal") or result.get("recommendation") or "NEUTRAL"
    confidence = result.get("confidence") or "Low"
    reason = result.get("recommendation_reason") or result.get("analysis") or "No signal reason generated."

    print("")
    print("=" * 72)
    print(f"STOCK: {symbol}")
    print(f"STATUS: {status}")
    print(f"SIGNAL: {signal}")
    print(f"CONFIDENCE: {confidence}")
    print(f"REASON: {reason}")
    print("=" * 72)
    print("")


def process_record(graph, record):
    symbol = record.get("SYMBOL", "")
    print(f"Analyzing {symbol}...")

    try:
        result = graph.invoke(initial_state(record))
    except Exception as e:
        print(f"{symbol}: FAILED - {e}")
        result = failed_state(record, e)

    print_recommendation(result)
    return result


def format_sleep(seconds):
    minutes, remaining_seconds = divmod(seconds, 60)
    return f"{minutes}:{remaining_seconds:02d}"


def refresh_nse_data():
    init_session()
    update_nse_master()


def run_cycle(graph):
    existing_results = load_results()
    records = load_records()
    pending_record = pick_next_unprocessed_record(records, existing_results)

    if not pending_record:
        print("No pending announcements to analyze.")
        return 0

    new_result = process_record(graph, pending_record)
    all_results = [new_result] + existing_results
    save_json_file(OUTPUT_FILE, all_results)
    print(f"Wrote recommendation to {OUTPUT_FILE}")
    return 1


def main(once=False):
    graph = build_graph()
    refresh_nse_data()

    while True:
        print("Starting research cycle...")
        processed_count = run_cycle(graph)

        if once:
            break

        if processed_count:
            print("Moving to next pending stock...")
            continue

        sleep_seconds = random.randint(MIN_SLEEP_SECONDS, MAX_SLEEP_SECONDS)
        print(f"Waiting {format_sleep(sleep_seconds)} before checking NSE again. Press Ctrl+C to stop.")
        time.sleep(sleep_seconds)
        refresh_nse_data()


def parse_args():
    parser = argparse.ArgumentParser(description="Run the NSE AI research recommendation loop.")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        main(once=args.once)
    except KeyboardInterrupt:
        print("\nStopped research loop.")
