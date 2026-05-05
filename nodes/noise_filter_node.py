import re
from utils.logger import log

# Tweets must contain at least one of these to be kept
_SIGNAL_KEYWORDS = frozenset({
    "results", "deal", "order", "acquisition", "stake", "profit", "loss",
    "revenue", "earnings", "quarterly", "annual", "capex", "expansion",
    "launch", "contract", "merger", "buyback", "dividend", "split", "bonus",
    "upgrade", "downgrade", "target", "guidance", "forecast", "investment",
    "raise", "fund", "ipo", "listing", "shares", "stock", "nse", "bse",
    "sensex", "nifty", "q1", "q2", "q3", "q4",
    # Regulatory / macro financial
    "tariff", "tariffs", "regulator", "regulators", "regulation", "sebi",
    "rbi", "irdai", "trai", "cerc", "penalty", "fine", "compliance",
    "policy", "rate", "hike", "cut", "inflation", "gdp", "fiscal",
    # Sector keywords (energy, infra, banking)
    "power", "electricity", "energy", "coal", "oil", "gas", "refinery",
    "telecom", "pharma", "bank", "insurance", "realty", "steel", "cement",
    # Major company names as bare keywords
    "reliance", "infosys", "wipro", "hdfc", "icici", "sbi", "bajaj",
    "maruti", "airtel", "adani", "tatasteel", "tatamotors", "hcltech",
    "sunpharma", "zomato", "kotak", "nestle", "titan", "itc", "l&t",
})

# Regex patterns whose match causes a tweet to be REJECTED
_REJECT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bvote\b", r"\belection\b", r"\bpolitics\b", r"\bminister\b",
        r"\bweather\b", r"\bsports\b", r"\bcricket\b", r"\bfestival\b",
        r"\bfollow us\b", r"\bsubscribe\b", r"\bjoin us\b", r"\bwatch live\b",
    ]
]

_URL_RE = re.compile(r"https?://\S+")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F]+",
    flags=re.UNICODE,
)
_WHITESPACE_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = _URL_RE.sub("", text)
    text = _EMOJI_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _is_relevant(text: str) -> bool:
    lower = text.lower()
    if any(p.search(lower) for p in _REJECT_PATTERNS):
        return False
    return any(kw in lower for kw in _SIGNAL_KEYWORDS)


def noise_filter_node(state: dict) -> dict:
    raw = state.get("raw_tweets", [])
    filtered = []

    for tweet in raw:
        clean = _clean(tweet.get("raw_text", ""))
        if _is_relevant(clean):
            filtered.append({
                "tweet_id": tweet["tweet_id"],
                "raw_text": tweet["raw_text"],
                "clean_text": clean,
                "author": tweet["author"],
                "created_at": tweet["created_at"],
                "account_weight": tweet.get("account_weight", 0.70),
            })

    state["filtered_tweets"] = filtered
    log("FILTER", f"{len(raw)} raw → {len(filtered)} relevant")
    return state
