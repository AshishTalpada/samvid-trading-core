import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class AntiSignalTracker:
    """
    Inverse Cramer / crowd error profitability engine.
    Tracks retail sentiment indicators and generates FADE signals when
    retail consensus reaches extreme levels (>85% bulls or bears).
    """
    def __init__(self, extreme_threshold: float = 0.85):
        self.threshold = extreme_threshold

    def compute_retail_sentiment(self, put_call_ratio: float, aaii_bull_pct: float, retail_flow_usd: float) -> float:
        pc_sentiment = 1.0 - min(1.0, put_call_ratio / 2.0)
        aaii_norm = aaii_bull_pct / 100.0
        flow_norm = min(1.0, max(0.0, retail_flow_usd / 1e9))
        return (pc_sentiment + aaii_norm + flow_norm) / 3.0

    def fade_signal(self, retail_sentiment: float) -> str:
        if retail_sentiment > self.threshold:
            logger.warning(f"[ANTI-SIGNAL] Extreme retail bullishness ({retail_sentiment:.0%}) → FADE LONG, go short.")
            return "FADE_LONG"
        if retail_sentiment < (1 - self.threshold):
            logger.warning(f"[ANTI-SIGNAL] Extreme retail bearishness ({retail_sentiment:.0%}) → FADE SHORT, go long.")
            return "FADE_SHORT"
        return "NEUTRAL"
