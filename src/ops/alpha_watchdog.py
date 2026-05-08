import numpy as np
import logging
from collections import deque

logger = logging.getLogger(__name__)

class AlphaDecayWatchdog:
    """
    Advanced Strategy Safety Monitor.
    Tracks the rolling performance (Sharpe Ratio and Return Distributions) of live strategies.
    If a strategy's edge begins to statistically decay due to market regime changes or
    institutional crowding, this watchdog automatically quarantines the strategy.
    """
    def __init__(self, history_window: int = 100):
        self.window = history_window
        self.trade_returns = deque(maxlen=history_window)
        self.baseline_sharpe = 0.0
        self.is_quarantined = False

    def ingest_trade(self, return_pct: float):
        self.trade_returns.append(return_pct)
        
        if len(self.trade_returns) >= self.window // 2:
            self._evaluate_decay()

    def _evaluate_decay(self):
        data = np.array(self.trade_returns)
        mean_ret = np.mean(data)
        std_ret = np.std(data)
        
        if std_ret == 0:
            return
            
        current_sharpe = (mean_ret * math.sqrt(252)) / std_ret # Annualized rough estimation
        
        # Set baseline if not established
        if self.baseline_sharpe == 0.0 and len(self.trade_returns) == self.window:
            self.baseline_sharpe = current_sharpe
            logger.info(f"[WATCHDOG] Baseline Sharpe established at {self.baseline_sharpe:.2f}")
            return

        # Check for structural decay
        if self.baseline_sharpe > 0:
            decay_pct = (self.baseline_sharpe - current_sharpe) / self.baseline_sharpe
            
            # If the strategy has lost 40% of its predictive power relative to history, it's decaying
            if decay_pct > 0.40 and current_sharpe < 1.0:
                logger.critical(f"[WATCHDOG] SEVERE ALPHA DECAY DETECTED! Sharpe dropped from {self.baseline_sharpe:.2f} to {current_sharpe:.2f}.")
                self._quarantine_strategy()

    def _quarantine_strategy(self):
        self.is_quarantined = True
        logger.critical("[WATCHDOG] STRATEGY QUARANTINED. All signal generation suspended. Awaiting human review or neuro-evolution rewrite.")
