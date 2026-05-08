import logging
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

TAX_RATES = {"us_short": 0.37, "us_long": 0.20, "uk": 0.20, "india_short": 0.15}

class RealTimeTaxTracker:
    """
    Tracks running tax liability in real time as trades are executed.
    Prevents end-of-year tax surprises by maintaining a live estimate of
    capital gains tax owed, separated by short-term and long-term lots.
    """
    def __init__(self, jurisdiction: str = "us"):
        self.jurisdiction = jurisdiction
        self._lots: List[Dict] = []
        self.running_tax_usd = 0.0

    def record_open(self, ticker: str, qty: float, price: float) -> None:
        self._lots.append({"ticker": ticker, "qty": qty, "basis": price, "opened_at": time.time()})

    def record_close(self, ticker: str, qty: float, exit_price: float) -> float:
        for lot in [l for l in self._lots if l["ticker"] == ticker]:
            pnl = (exit_price - lot["basis"]) * min(qty, lot["qty"])
            hold_days = (time.time() - lot["opened_at"]) / 86400
            rate_key = "us_long" if hold_days >= 365 else "us_short"
            tax = max(0.0, pnl * TAX_RATES.get(rate_key, 0.37))
            self.running_tax_usd += tax
            logger.info(f"[TAX TRACKER] {ticker} PnL=${pnl:.2f} Tax=${tax:.2f} YTD=${self.running_tax_usd:.2f}")
            return tax  # type: ignore
        return 0.0
