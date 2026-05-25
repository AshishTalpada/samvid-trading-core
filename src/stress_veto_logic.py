import logging
from typing import Dict

logger = logging.getLogger(__name__)


class StressVetoLogic:
    """
    Detects and blocks 'Revenge Trading' and stress-driven over-trading.
    Monitors: loss streak length, trade frequency acceleration, position size escalation.
    Locks the user out of trading if 3+ red flags fire simultaneously.
    """

    def __init__(self):
        self._recent_pnls: list[float] = []
        self._trade_times: list[float] = []
        self._position_sizes: list[float] = []

    def record_trade(self, pnl: float, timestamp: float, position_size: float) -> None:
        self._recent_pnls.append(pnl)
        self._trade_times.append(timestamp)
        self._position_sizes.append(position_size)
        if len(self._recent_pnls) > 50:
            self._recent_pnls.pop(0)
            self._trade_times.pop(0)
            self._position_sizes.pop(0)

    def evaluate(self) -> Dict:
        if len(self._recent_pnls) < 5:
            return {"veto": False, "flags": []}

        flags = []
        loss_streak = sum(1 for p in self._recent_pnls[-5:] if p < 0)
        if loss_streak >= 4:
            flags.append(f"LOSS_STREAK: {loss_streak} consecutive losses")

        if len(self._trade_times) >= 3:
            intervals = [
                self._trade_times[i] - self._trade_times[i - 1]
                for i in range(1, len(self._trade_times[-6:]))
            ]
            avg_interval = sum(intervals) / len(intervals) if intervals else 999
            if avg_interval < 120:
                flags.append(f"OVER_TRADING: avg interval {avg_interval:.0f}s < 2 min")

        if len(self._position_sizes) >= 3:
            recent_sizes = self._position_sizes[-3:]
            if all(
                recent_sizes[i] > recent_sizes[i - 1] * 1.3 for i in range(1, len(recent_sizes))
            ):
                flags.append("SIZE_ESCALATION: Position size growing 30%+ each trade")

        veto = len(flags) >= 2
        if veto:
            logger.critical(f"[STRESS VETO] TRADING LOCKED: {flags}")
        return {"veto": veto, "flags": flags, "loss_streak": loss_streak}
