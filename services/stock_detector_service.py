import json
import re
from pathlib import Path
from typing import Dict, List, Optional

NSE_MASTER_PATH = Path("data/nse_master.json")

# Hardcoded aliases for high-traffic stocks (name/abbreviation → NSE symbol)
_ALIASES: Dict[str, str] = {
    "reliance": "RELIANCE", "ril": "RELIANCE", "mukesh ambani": "RELIANCE",
    "tcs": "TCS", "tata consultancy": "TCS", "tata consulting": "TCS",
    "infosys": "INFY", "infy": "INFY",
    "wipro": "WIPRO",
    "hcl": "HCLTECH", "hcl technologies": "HCLTECH", "hcltech": "HCLTECH",
    "tech mahindra": "TECHM",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK",
    "icici bank": "ICICIBANK", "icici": "ICICIBANK",
    "axis bank": "AXISBANK",
    "kotak bank": "KOTAKBANK", "kotak mahindra bank": "KOTAKBANK", "kotak": "KOTAKBANK",
    "sbi": "SBIN", "state bank": "SBIN", "state bank of india": "SBIN",
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE",
    "bajaj finserv": "BAJAJFINSV",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "jsw steel": "JSWSTEEL", "jsw": "JSWSTEEL",
    "hindalco": "HINDALCO",
    "vedanta": "VEDL",
    "ongc": "ONGC", "oil and natural gas": "ONGC",
    "coal india": "COALINDIA",
    "ntpc": "NTPC",
    "power grid": "POWERGRID",
    "airtel": "BHARTIARTL", "bharti airtel": "BHARTIARTL", "bhartiartl": "BHARTIARTL",
    "hul": "HINDUNILVR", "hindustan unilever": "HINDUNILVR",
    "itc": "ITC",
    "nestle india": "NESTLEIND", "nestle": "NESTLEIND",
    "britannia": "BRITANNIA",
    "asian paints": "ASIANPAINT", "asian paint": "ASIANPAINT",
    "l&t": "LT", "larsen": "LT", "larsen & toubro": "LT", "larsen and toubro": "LT",
    "maruti": "MARUTI", "maruti suzuki": "MARUTI", "msil": "MARUTI",
    "titan": "TITAN",
    "sun pharma": "SUNPHARMA", "sun pharmaceutical": "SUNPHARMA",
    "dr reddy": "DRREDDY", "dr. reddy": "DRREDDY",
    "cipla": "CIPLA",
    "divi's": "DIVISLAB", "divi laboratories": "DIVISLAB",
    "adani": "ADANIENT", "adani enterprises": "ADANIENT", "gautam adani": "ADANIENT",
    "adani ports": "ADANIPORTS",
    "adani green": "ADANIGREEN",
    "adani total": "ADANITOTAL",
    "zomato": "ZOMATO",
    "nykaa": "NYKAA",
    "paytm": "PAYTM", "one97": "PAYTM",
    "ola electric": "OLAELEC",
    "swiggy": "SWIGGY",
    "ultracemco": "ULTRACEMCO", "ultratech cement": "ULTRACEMCO", "ultratech": "ULTRACEMCO",
}

# Words too generic to use as stock aliases from company names
_STOP_WORDS = frozenset({
    "limited", "india", "private", "public", "finance", "bank", "group",
    "industries", "enterprises", "solutions", "services", "technologies",
    "international", "holdings", "corporation", "company", "infrastructure",
    "capital", "energy", "power", "resources",
})

_lookup_cache: Optional[Dict[str, str]] = None


def _build_lookup() -> Dict[str, str]:
    lookup: Dict[str, str] = {}

    if NSE_MASTER_PATH.exists():
        try:
            with NSE_MASTER_PATH.open("r", encoding="utf-8") as f:
                records = json.load(f)
            seen_companies: set = set()
            for record in records:
                symbol = (record.get("SYMBOL") or "").strip().upper()
                company = (record.get("COMPANY NAME") or "").lower()
                if not symbol:
                    continue
                # Exact symbol match (e.g. "TCS" in tweet)
                lookup[symbol.lower()] = symbol
                # Single-word tokens from company name
                if company not in seen_companies:
                    seen_companies.add(company)
                    for word in re.findall(r"\b[a-z]{4,}\b", company):
                        if word not in _STOP_WORDS and word not in lookup:
                            lookup[word] = symbol
        except Exception:
            pass

    # Hardcoded aliases always win (longer phrases first so they match before subwords)
    for alias, symbol in _ALIASES.items():
        lookup[alias.lower()] = symbol

    return lookup


def _get_lookup() -> Dict[str, str]:
    global _lookup_cache
    if _lookup_cache is None:
        _lookup_cache = _build_lookup()
    return _lookup_cache


def detect_stocks(text: str) -> List[str]:
    """Return deduplicated list of NSE symbols found in *text*."""
    lookup = _get_lookup()
    text_lower = text.lower()
    found: set = set()

    # Sort by length descending so multi-word aliases match before single words
    for term in sorted(lookup, key=len, reverse=True):
        pattern = r"(?<![a-z])" + re.escape(term) + r"(?![a-z])"
        if re.search(pattern, text_lower):
            found.add(lookup[term])

    return list(found)


def reload_lookup() -> None:
    """Force re-build of the lookup (call after updating nse_master.json)."""
    global _lookup_cache
    _lookup_cache = None
