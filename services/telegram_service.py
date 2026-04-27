import os

import requests


def send_telegram_message(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    res = requests.post(url, json=payload, timeout=20)
    if not res.ok:
        raise RuntimeError(f"Telegram send failed HTTP {res.status_code}: {res.text[:500]}")
    return res.json()


def get_latest_chat_ids():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    res = requests.get(url, timeout=20)
    if not res.ok:
        raise RuntimeError(f"Telegram getUpdates failed HTTP {res.status_code}: {res.text[:500]}")

    chat_ids = []
    for update in res.json().get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id and chat_id not in chat_ids:
            chat_ids.append(chat_id)

    return chat_ids
