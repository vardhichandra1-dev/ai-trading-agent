import os
from kiteconnect import KiteConnect

def get_quote(symbol):
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")
    if not api_key or not access_token:
        raise ValueError("KITE_API_KEY and KITE_ACCESS_TOKEN must be set")

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    s = f"NSE:{symbol}"
    data = kite.quote(s)[s]

    return {
        "ltp": data["last_price"],
        "open": data["ohlc"]["open"],
        "high": data["ohlc"]["high"],
        "low": data["ohlc"]["low"],
        "close": data["ohlc"]["close"],
        "volume": data["volume"],
        "change": data["net_change"]
    }
