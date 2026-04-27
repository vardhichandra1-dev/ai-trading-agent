from dotenv import load_dotenv

from services.telegram_service import send_telegram_message


def main():
    load_dotenv(".env")
    send_telegram_message(
        "Stock: TEST\n"
        "Signal: BUY\n"
        "Confidence: High\n"
        "Reason: Telegram notification test from AI research agent."
    )
    print("Telegram test message sent.")


if __name__ == "__main__":
    main()
