import logging
from collections import deque
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class FootprintAuditor:
    """
    Detects institutional accumulation/distribution via order-flow imbalance
    without price movement (stealth accumulation).
    Uses delta (Buy Volume - Sell Volume) clustering to identify hidden intent.
    """

    def __init__(self, lookback_bars: int = 20):
        self.lookback = lookback_bars
        self._deltas: deque[float] = deque(maxlen=lookback_bars)

    def record_bar(self, buy_volume: float, sell_volume: float) -> None:
        self._deltas.append(buy_volume - sell_volume)

    def cumulative_delta(self) -> float:
        return float(sum(self._deltas))

    def detect_hidden_accumulation(self, price_change_pct: float, delta_threshold: float = 0.0) -> Dict:
        if len(self._deltas) < self.lookback:
            return {"signal": "INSUFFICIENT_DATA"}
        cum_delta = self.cumulative_delta()
        # Hidden accumulation: positive delta but flat/negative price = someone buying quietly
        hidden_acc = cum_delta > delta_threshold and price_change_pct < 0.005
        hidden_dist = cum_delta < -delta_threshold and price_change_pct > -0.005
        signal = "HIDDEN_ACCUMULATION" if hidden_acc else "HIDDEN_DISTRIBUTION" if hidden_dist else "NEUTRAL"
        if signal != "NEUTRAL":
            logger.info(f"[FOOTPRINT] {signal}: delta={cum_delta:.0f}, price_chg={price_change_pct:.3%}")
        return {"signal": signal, "cumulative_delta": round(cum_delta, 2), "price_change_pct": round(price_change_pct, 4)}
