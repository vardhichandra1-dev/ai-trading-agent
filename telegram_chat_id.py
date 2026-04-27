from dotenv import load_dotenv

from services.telegram_service import get_latest_chat_ids


def main():
    load_dotenv(".env")
    chat_ids = get_latest_chat_ids()

    if not chat_ids:
        print("No Telegram chats found. Open your bot in Telegram, send /start, then run this again.")
        return

    print("Telegram chat ids found:")
    for chat_id in chat_ids:
        print(chat_id)


if __name__ == "__main__":
    main()
