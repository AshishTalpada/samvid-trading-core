import logging
import math
from collections import deque
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AlphaDecayWatchdog:
    """
    Advanced Strategy Safety Monitor.
    Tracks the rolling performance (Sharpe Ratio and Return Distributions) of live strategies.
    If a strategy's edge begins to statistically decay due to market regime changes or
    institutional crowding, this watchdog automatically quarantines the strategy.
    """

    def __init__(self, bridge: Any = None, history_window: int = 100):
        self.bridge = bridge
        self.window = history_window
        self.trade_returns: Any = deque(maxlen=history_window)
        self.baseline_sharpe = 0.0
        self.is_quarantined = False

    async def ingest_trade(self, return_pct: float):
        self.trade_returns.append(return_pct)

        if len(self.trade_returns) >= self.window // 2:
            await self._evaluate_decay()

    async def _evaluate_decay(self):
        data = np.array(self.trade_returns)
        mean_ret = np.mean(data)
        std_ret = np.std(data)

        if std_ret == 0:
            return

        # Improved Sharpe: Adjust for trade frequency if possible,
        # or treat as per-trade Information Ratio.
        # We use sqrt(252) as a loose proxy for daily-equivalent return.
        current_sharpe = (mean_ret * math.sqrt(252)) / std_ret

        # Set baseline if not established
        if self.baseline_sharpe == 0.0 and len(self.trade_returns) == self.window:
            self.baseline_sharpe = current_sharpe
            logger.info(f"[WATCHDOG] Baseline Sharpe established at {self.baseline_sharpe:.2f}")
            return

        # Check for structural decay
        if self.baseline_sharpe > 0.5:  # Only track decay for meaningful baselines
            decay_pct = (self.baseline_sharpe - current_sharpe) / self.baseline_sharpe
            if decay_pct > 0.40 and current_sharpe < 1.0:
                logger.critical(
                    f"[WATCHDOG] SEVERE ALPHA DECAY DETECTED! Sharpe dropped from {self.baseline_sharpe:.2f} to {current_sharpe:.2f}."
                )
                await self._quarantine_strategy()
        elif self.baseline_sharpe <= 0.5 and current_sharpe < -2.0:
            logger.critical(
                f"[WATCHDOG] STRATEGY COLLAPSE! Sharpe collapsed to {current_sharpe:.2f}."
            )
            await self._quarantine_strategy()

    async def _quarantine_strategy(self):
        self.is_quarantined = True
        logger.critical("[WATCHDOG] STRATEGY QUARANTINED. All signal generation suspended.")

        if self.bridge:
            await self.bridge.broadcast(
                "watchdog",
                "CRITICAL: Strategy Quarantine Triggered due to Alpha Decay.",
                {"type": "QUARANTINE", "state": True},
            )
