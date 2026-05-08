import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class RDVelocityAgent:
    """
    R&D / Patent Velocity Agent.
    Tracks the speed of new patent filings (via USPTO feeds) for tech hardware.
    A sudden spike in patent velocity indicates a major product breakthrough
    (like Apple's M1 chip) 12-18 months before earnings reflection.
    """
    def __init__(self, lookback_months: int = 12):
        self.lookback = lookback_months
        self.filing_history: Dict[str, List[int]] = {}

    def register_monthly_filings(self, ticker: str, count: int) -> None:
        if ticker not in self.filing_history:
            self.filing_history[ticker] = []
        self.filing_history[ticker].append(count)
        if len(self.filing_history[ticker]) > self.lookback * 2:
            self.filing_history[ticker].pop(0)

    def estimate_velocity(self, ticker: str) -> float:
        history = self.filing_history.get(ticker, [])
        if len(history) < self.lookback:
            return 0.0

        import numpy as np
        recent = np.sum(history[-6:])  # Last 6 months
        past = np.sum(history[-12:-6]) # Previous 6 months

        if past == 0:
            return 0.0

        velocity = (recent - past) / past

        if velocity > 0.5:
            logger.info(f"[R&D AGENT] Major innovation spike for {ticker}: {velocity:+.0%} filing velocity.")

        return float(velocity)
