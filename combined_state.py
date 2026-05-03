from typing import TypedDict


class CombinedState(TypedDict):
    run_id: str

    # ── NSE pipeline outcome ──────────────────────────────────────────────────
    nse_status: str          # NO_PENDING | SUCCESS | FAILED
    nse_symbol: str          # stock processed this cycle
    nse_signal: str          # BUY / SELL / NEUTRAL
    nse_telegram_sent: bool
    nse_error: str

    # ── Twitter pipeline outcome ──────────────────────────────────────────────
    twitter_status: str      # SUCCESS | FAILED
    twitter_summaries_count: int
    twitter_alerts_sent: int
    twitter_error: str
