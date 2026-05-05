import re

# ── Order / contract keywords ─────────────────────────────────────────────────

PRIMARY_ORDER_KEYWORDS = [
    # NSE announcement category names
    "bagging/receipt of orders",
    "receipt of orders",
    "award of contract",
    # Action verb + order/contract
    "secured order", "secured contract",
    "bagged order", "bagged contract",
    "won order", "won contract",
    "received order", "received contract",
    "order received", "contract received",
    "awarded contract", "awarded order",
    "new order",
    "order win", "order wins",
    # Letter of Award / Intent
    "letter of award", "letter of intent",
    " loa ", " loi ",
    # Work / purchase orders
    "work order", "purchase order",
    # EPC / turnkey
    "epc contract", "epc order",
]

ORDER_NEGATIVE_KEYWORDS = [
    "order-in-appeal", "order in appeal",
    "court order", "tribunal order",
    "gst order", "under gst",
    "sebi order", "cci order", "cerc order",
    "penalty order", "show cause",
    "suo motu", "interim order",
    "stay order", "injunction",
    "arbitration award", "contempt",
    "regulatory order", "compliance order",
    "orders passed",
    "order passed",
    "order disposed",
]

BUSINESS_CONTEXT_KEYWORDS = [
    "project", "supply", "execution", "client",
    "construction", "installation", "infrastructure",
    "manufacturing", "procurement", "services",
    "works", "turnkey", "erection", "commissioning",
    "solar", "power", "road", "highway", "metro",
    "railway", "defence", "government", "municipal",
    "hospital", "building", "plant", "facility",
]

VALUE_KEYWORDS = [
    "crore", "cr.", " cr ",
    "million", " mn ",
    "lakh", "lakhs",
    "billion",
    "worth", "valued at", "value of",
    "₹", "rs.",
]

_ORDER_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"secured?\s+(?:an?\s+)?(?:order|contract)",
        r"bagged?\s+(?:an?\s+)?(?:order|contract)",
        r"awarded?\s+(?:an?\s+)?(?:order|contract|project)",
        r"received?\s+(?:an?\s+)?(?:order|contract|loa|loi)",
        r"won\s+(?:an?\s+)?(?:order|contract|bid)",
        r"new\s+orders?\s+(?:worth|of|for|from)",
        r"orders?\s+(?:worth|valued|of)\s+(?:₹|rs\.?|\d)",
    ]
]


# ── Acquisition / M&A keywords ────────────────────────────────────────────────

ACQUISITION_KEYWORDS = [
    "acquisition", "acquire", "acquired", "acquiring",
    "buyout", "takeover",
    "merger", "amalgamation",
    "scheme of arrangement",
    "business transfer", "slump sale",
    "strategic investment",
    "investment in",
    "stake acquisition",
    "equity stake", "majority stake", "minority stake",
    "purchase of shares",
    "subscription to shares",
]

ACQUISITION_CONTEXT_KEYWORDS = [
    "subsidiary", "target company",
    "valuation", "deal value",
    "enterprise value", "cash consideration",
    "share swap", "board approval",
    "binding agreement", "definitive agreement",
]

ACQUISITION_NEGATIVE_KEYWORDS = [
    "rumor", "rumour",
    "speculation", "speculative",
    "media report", "media reports",
    "denies", "denied", "deny",
    "no acquisition",
    "withdrawn", "withdrawal",
    "clarification",
]

_ACQUISITION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"acquir(?:e|ed|ing)\s+\d+\s*%",
        r"acquir(?:e|ed|ing)\s+(?:stake|shares?|equity)",
        r"(?:majority|minority|controlling)\s+stake\s+in",
        r"merger\s+(?:with|of|between)",
        r"scheme\s+of\s+(?:arrangement|merger|amalgamation)",
    ]
]


# ── Individual scorers ────────────────────────────────────────────────────────

def _score_order(lower: str) -> dict:
    if any(k in lower for k in ORDER_NEGATIVE_KEYWORDS):
        return {
            "event_type": "order_win",
            "score": 0.0,
            "status": "REJECT",
            "reason": "order: legal/compliance keyword detected",
        }

    has_primary = (
        any(k in lower for k in PRIMARY_ORDER_KEYWORDS)
        or any(p.search(lower) for p in _ORDER_PATTERNS)
    )
    has_business = any(k in lower for k in BUSINESS_CONTEXT_KEYWORDS)
    has_value = any(k in lower for k in VALUE_KEYWORDS)

    score = 0.0
    if has_primary:
        score += 0.5
    if has_business:
        score += 0.2
    if has_value:
        score += 0.2
    score += 0.1  # no negative keyword (already checked above)

    reason = (
        f"order: primary={'Y' if has_primary else 'N'} "
        f"business={'Y' if has_business else 'N'} "
        f"value={'Y' if has_value else 'N'} "
        f"score={round(score, 2)}"
    )
    return {
        "event_type": "order_win",
        "score": round(score, 2),
        "status": "PASS" if score >= 0.7 else "REJECT",
        "reason": reason,
    }


def _score_acquisition(lower: str) -> dict:
    if any(k in lower for k in ACQUISITION_NEGATIVE_KEYWORDS):
        return {
            "event_type": "acquisition",
            "score": 0.0,
            "status": "REJECT",
            "reason": "acquisition: denial/rumor keyword detected",
        }

    has_primary = (
        any(k in lower for k in ACQUISITION_KEYWORDS)
        or any(p.search(lower) for p in _ACQUISITION_PATTERNS)
    )
    has_context = any(k in lower for k in ACQUISITION_CONTEXT_KEYWORDS)

    score = 0.0
    if has_primary:
        score += 0.6
    if has_context:
        score += 0.3
    score += 0.1  # no negative keyword

    reason = (
        f"acquisition: primary={'Y' if has_primary else 'N'} "
        f"context={'Y' if has_context else 'N'} "
        f"score={round(score, 2)}"
    )
    return {
        "event_type": "acquisition",
        "score": round(score, 2),
        "status": "PASS" if score >= 0.7 else "REJECT",
        "reason": reason,
    }


# ── Public interface ──────────────────────────────────────────────────────────

def filter_order(record: dict) -> dict:
    """Score a single NSE announcement for order wins OR acquisitions.

    Runs both detectors and picks the higher-scoring passing result.
    Returns: {stock, event_type, confidence, timestamp, status, score, reason}
    """
    subject = record.get("SUBJECT", "") or ""
    details = record.get("DETAILS", "") or ""
    lower = f"{subject} {details}".lower()

    order_result = _score_order(lower)
    acq_result = _score_acquisition(lower)

    # Pick winner: prefer the passing result with the highest score
    candidates = [r for r in (order_result, acq_result) if r["status"] == "PASS"]
    if candidates:
        winner = max(candidates, key=lambda r: r["score"])
    else:
        # Both rejected — return whichever scored higher for diagnostics
        winner = max((order_result, acq_result), key=lambda r: r["score"])

    return {
        "stock": record.get("SYMBOL", ""),
        "event_type": winner["event_type"],
        "confidence": winner["score"],
        "timestamp": record.get("BROADCAST DATE/TIME", ""),
        "status": winner["status"],
        "score": winner["score"],
        "reason": winner["reason"],
    }
