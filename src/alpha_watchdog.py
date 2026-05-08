"""
Alpha Watchdog (#149 from SOVEREIGN_ULTIMATE_CHECKLIST).
Monitors when a strategy starts losing its mathematical edge.
"""

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AlphaMetrics:
    """Alpha/edge metrics for a strategy."""
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_approx: float
    edge_confidence: float
    decay_detected: bool
    recommendation: str


class AlphaWatchdog:
    """
    Strategy Alpha Monitoring System.
    
    Tracks strategy performance metrics and alerts when the mathematical
    edge starts degrading (alpha decay).
    """

    MIN_SAMPLE_SIZE = 20
    DECAY_THRESHOLD = 0.15
    CONFIDENCE_WINDOW = 50

    def __init__(self):
        self.performance_history = deque(maxlen=500)
        self.baseline_metrics: Optional[AlphaMetrics] = None

    def record_trade(self, pnl: float, confidence: float = 1.0):
        """Record a trade result for analysis."""
        self.performance_history.append({
            "pnl": pnl,
            "confidence": confidence,
            "timestamp": np.datetime64("now").astype(float),
        })

    def calculate_metrics(self) -> Optional[AlphaMetrics]:
        """Calculate current strategy metrics."""
        if len(self.performance_history) < self.MIN_SAMPLE_SIZE:
            return None

        recent = list(self.performance_history)[-self.CONFIDENCE_WINDOW:]

        pnls = [t["pnl"] for t in recent]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / len(pnls) if pnls else 0.5
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 1

        profit_factor = (avg_win * len(wins)) / (avg_loss * len(losses)) if losses and avg_loss > 0 else 1

        returns = np.array(pnls)
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        edge_confidence = self._calculate_edge_confidence(win_rate, avg_win, avg_loss, profit_factor)

        decay_detected = self._detect_decay()

        recommendation = self._get_recommendation(profit_factor, sharpe, edge_confidence, decay_detected)

        return AlphaMetrics(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_approx=sharpe,
            edge_confidence=edge_confidence,
            decay_detected=decay_detected,
            recommendation=recommendation,
        )

    def _calculate_edge_confidence(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        profit_factor: float,
    ) -> float:
        """Calculate confidence in the strategy's edge (0-1)."""
        if self.baseline_metrics is None:
            return 0.5

        baseline = self.baseline_metrics

        win_rate_change = abs(win_rate - baseline.win_rate) / max(baseline.win_rate, 0.01)
        pf_change = abs(profit_factor - baseline.profit_factor) / max(baseline.profit_factor, 0.01)

        confidence = 1.0 - min(1.0, (win_rate_change + pf_change) / 2)

        return max(0.0, min(1.0, confidence))

    def _detect_decay(self) -> bool:
        """Detect if alpha is decaying compared to baseline."""
        if self.baseline_metrics is None:
            return False

        if len(self.performance_history) < self.MIN_SAMPLE_SIZE * 2:
            return False

        recent = list(self.performance_history)[-self.MIN_SAMPLE_SIZE:]
        earlier = list(self.performance_history)[-2*self.MIN_SAMPLE_SIZE:-self.MIN_SAMPLE_SIZE]

        recent_pnls = [t["pnl"] for t in recent]
        earlier_pnls = [t["pnl"] for t in earlier]

        recent_return = np.mean(recent_pnls)
        earlier_return = np.mean(earlier_pnls)

        if earlier_return <= 0:
            return False

        decay_ratio = (earlier_return - recent_return) / abs(earlier_return)

        return decay_ratio > self.DECAY_THRESHOLD

    def _get_recommendation(
        self,
        profit_factor: float,
        sharpe: float,
        edge_confidence: float,
        decay_detected: bool,
    ) -> str:
        """Get recommendation based on metrics."""
        if decay_detected:
            return "INVESTIGATE_DECAY"
        elif profit_factor < 1.2 or sharpe < 0.5:
            return "REDUCE_SIZE"
        elif edge_confidence < 0.4:
            return "VERIFY_STRATEGY"
        elif profit_factor > 2.0 and sharpe > 1.5:
            return "INCREASE_SIZE"
        else:
            return "MAINTAIN"

    def set_baseline(self):
        """Set current metrics as baseline for future comparison."""
        metrics = self.calculate_metrics()
        if metrics:
            self.baseline_metrics = metrics
            logger.info(f"Alpha baseline set: PF={metrics.profit_factor:.2f}, WR={metrics.win_rate:.2%}")

    def compare_to_baseline(self) -> dict[str, Any]:
        """Compare current performance to baseline."""
        if self.baseline_metrics is None:
            return {"status": "NO_BASELINE"}

        current = self.calculate_metrics()
        if current is None:
            return {"status": "INSUFFICIENT_DATA"}

        return {
            "status": "COMPARING",
            "baseline": {
                "profit_factor": self.baseline_metrics.profit_factor,
                "win_rate": self.baseline_metrics.win_rate,
                "sharpe": self.baseline_metrics.sharpe_approx,
            },
            "current": {
                "profit_factor": current.profit_factor,
                "win_rate": current.win_rate,
                "sharpe": current.sharpe_approx,
            },
            "changes": {
                "profit_factor_change": (current.profit_factor - self.baseline_metrics.profit_factor) / self.baseline_metrics.profit_factor,
                "win_rate_change": current.win_rate - self.baseline_metrics.win_rate,
                "sharpe_change": current.sharpe_approx - self.baseline_metrics.sharpe_approx,
            },
            "decay_detected": current.decay_detected,
            "recommendation": current.recommendation,
        }

    def get_performance_summary(self) -> dict[str, Any]:
        """Get overall performance summary."""
        if not self.performance_history:
            return {"status": "NO_DATA"}

        pnls = [t["pnl"] for t in self.performance_history]

        return {
            "total_trades": len(pnls),
            "total_pnl": sum(pnls),
            "avg_pnl": np.mean(pnls),
            "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
            "max_drawdown": abs(min(np.cumsum(pnls))),
            "recent_performance": list(pnls)[-20:] if len(pnls) >= 20 else list(pnls),
        }


_alpha_watchdog_instance: Optional[AlphaWatchdog] = None


def get_alpha_watchdog() -> AlphaWatchdog:
    """Get the singleton AlphaWatchdog instance."""
    global _alpha_watchdog_instance
    if _alpha_watchdog_instance is None:
        _alpha_watchdog_instance = AlphaWatchdog()
    return _alpha_watchdog_instance
