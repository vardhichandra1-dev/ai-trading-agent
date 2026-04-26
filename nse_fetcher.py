import json
import os
import time

import pandas as pd
import requests

BASE_URL = "https://www.nseindia.com"
API_URL = "https://www.nseindia.com/api/corporate-announcements"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com/",
}

DATA_FILE = "data/nse_master.json"
SEEN_FILE = "data/seen_ids.json"

os.makedirs("data", exist_ok=True)

session = requests.Session()
session.headers.update(HEADERS)


def init_session():
    try:
        session.get(BASE_URL, timeout=10).raise_for_status()
        time.sleep(2)
    except Exception as e:
        print("Session init error:", e)


def fetch_data():
    try:
        res = session.get(API_URL + "?index=equities", timeout=10)
        res.raise_for_status()

        if "application/json" not in res.headers.get("Content-Type", ""):
            print("Blocked or invalid NSE response")
            return []

        return res.json()

    except Exception as e:
        print("Fetch error:", e)
        return []


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


def load_json():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_json(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def transform(item):
    try:
        dt = pd.to_datetime(item.get("an_dt")).isoformat()
    except Exception:
        dt = None

    attachment = item.get("attchmntFile")
    if attachment:
        attachment = str(attachment)
        if not attachment.startswith("http"):
            attachment = BASE_URL + attachment

        if "https://www.nseindia.comhttps://" in attachment:
            attachment = attachment.replace("https://www.nseindia.com", "")

    return {
        "SYMBOL": item.get("symbol"),
        "COMPANY NAME": item.get("sm_name"),
        "SUBJECT": item.get("desc"),
        "DETAILS": item.get("attchmntText"),
        "BROADCAST DATE/TIME": dt,
        "ATTACHMENT": attachment,
    }


def update_nse_master():
    print("Fetching NSE data...")

    data = fetch_data()
    if not data:
        print("No data fetched")
        return

    seen = load_seen()
    existing = load_json()
    new_records = []

    for item in data:
        uid = f"{item.get('an_dt')}_{item.get('seq_id')}"

        if uid not in seen:
            seen.add(uid)
            new_records.append(transform(item))

    if not new_records:
        print("No new updates")
        return

    combined = existing + new_records
    combined.sort(key=lambda x: x["BROADCAST DATE/TIME"] or "", reverse=True)
    combined = combined[:1000]

    save_json(combined)
    save_seen(seen)

    print(f"Added {len(new_records)} new records")


if __name__ == "__main__":
    init_session()
    update_nse_master()
