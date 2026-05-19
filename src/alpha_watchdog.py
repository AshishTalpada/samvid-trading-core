import logging
import math
import statistics
from collections import deque
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class AlphaDecayWatchdog:
    """
    Monitors every active strategy's live Sharpe ratio against its historical baseline.
    Raises a DECAY alert when rolling 20-day Sharpe drops more than 40% below the 90-day mean.
    Triggers RETIRE when Sharpe goes negative for 5 consecutive days.
    """

    def __init__(
        self, decay_threshold: float = 0.40, lookback_fast: int = 20, lookback_slow: int = 90
    ):
        self.decay_threshold = decay_threshold
        self.fast = lookback_fast
        self.slow = lookback_slow
        self._pnl: Dict[str, deque] = {}
        self._alert_counts: Dict[str, int] = {}

    def record(self, strategy_id: str, daily_pnl: float) -> None:
        if strategy_id not in self._pnl:
            self._pnl[strategy_id] = deque(maxlen=self.slow)
            self._alert_counts[strategy_id] = 0
        self._pnl[strategy_id].append(daily_pnl)

    def _sharpe(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean = statistics.mean(returns)
        std = statistics.stdev(returns)
        return (mean / std * math.sqrt(252)) if std > 0 else 0.0

    def evaluate(self, strategy_id: str) -> Dict:
        buf = list(self._pnl.get(strategy_id, []))
        if len(buf) < self.fast:
            return {"status": "WARMING_UP", "fast_sharpe": 0.0, "slow_sharpe": 0.0}

        fast_sharpe = self._sharpe(buf[-self.fast :])
        slow_sharpe = self._sharpe(buf) if len(buf) >= self.slow else fast_sharpe

        decay_ratio = (
            (slow_sharpe - fast_sharpe) / (abs(slow_sharpe) + 1e-9) if slow_sharpe != 0 else 0
        )
        consecutive_neg = sum(1 for p in buf[-5:] if p < 0)

        if consecutive_neg >= 5:
            status = "RETIRE"
        elif decay_ratio > self.decay_threshold:
            self._alert_counts[strategy_id] += 1
            status = "DECAY"
        else:
            self._alert_counts[strategy_id] = 0
            status = "HEALTHY"

        if status != "HEALTHY":
            logger.warning(
                f"[WATCHDOG] {strategy_id}: {status} | Fast={fast_sharpe:.2f} Slow={slow_sharpe:.2f} Decay={decay_ratio:.0%}"
            )

        return {
            "status": status,
            "fast_sharpe": round(fast_sharpe, 3),
            "slow_sharpe": round(slow_sharpe, 3),
            "decay_ratio": round(decay_ratio, 3),
            "consecutive_negative_days": consecutive_neg,
        }
