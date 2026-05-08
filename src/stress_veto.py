"""
Stress Veto (#214 from SOVEREIGN_ULTIMATE_CHECKLIST).
Detects 'Revenge Trading' patterns and locks the user out when detected.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a single trade for analysis."""
    timestamp: float
    symbol: str
    pnl: float
    size: float
    reason: str
    manual_override: bool = False


@dataclass
class StressAnalysis:
    """Result of stress/veto analysis."""
    stress_detected: bool
    stress_type: str
    severity: float
    recommendation: str
    reason: str
    cooldown_minutes: int


class StressVeto:
    """
    Psychology Safety System - Detects revenge trading and other stress patterns.

    Monitors:
    - Rapid consecutive trades after loss
    - Increasing trade size after losses
    - Trading outside normal hours
    - Manual overrides increasing
    - Pattern of "chasing" the market
    """

    CONSECUTIVE_LOSS_THRESHOLD = 3
    SIZE_INCREASE_THRESHOLD = 2.0
    RAPID_TRADE_WINDOW_MINUTES = 10
    MAX_TRADES_PER_HOUR = 15
    COOLDOWN_AFTER_VETO = 60

    def __init__(self):
        self.trade_history: deque[TradeRecord] = deque(maxlen=200)
        self.veto_count = 0
        self.last_veto_time = 0.0
        self.consecutive_losses = 0

    def record_trade(
        self,
        symbol: str,
        pnl: float,
        size: float,
        reason: str = "",
        manual_override: bool = False,
    ):
        """Record a trade for analysis."""
        trade = TradeRecord(
            timestamp=time.time(),
            symbol=symbol,
            pnl=pnl,
            size=size,
            reason=reason,
            manual_override=manual_override,
        )
        self.trade_history.append(trade)

        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def analyze_stress(self, current_hour: int | None = None) -> StressAnalysis:
        """
        Analyze recent trading for stress patterns.

        Args:
            current_hour: Current hour (0-23), defaults to system time

        Returns:
            StressAnalysis with veto recommendation
        """
        now = time.time()

        if now - self.last_veto_time < self.COOLDOWN_AFTER_VETO * 60:
            remaining = int((self.COOLDOWN_AFTER_VETO * 60 - (now - self.last_veto_time)) / 60)
            return StressAnalysis(
                stress_detected=True,
                stress_type="ACTIVE_VETO",
                severity=1.0,
                recommendation="LOCKOUT",
                reason=f"Active veto - {remaining} min remaining",
                cooldown_minutes=remaining,
            )

        recent_trades = self._get_recent_trades(self.RAPID_TRADE_WINDOW_MINUTES)

        if len(recent_trades) < 3:
            return StressAnalysis(
                stress_detected=False,
                stress_type="NORMAL",
                severity=0.0,
                recommendation="ALLOW",
                reason="Insufficient trade history for analysis",
                cooldown_minutes=0,
            )

        stress_type, severity = self._check_consecutive_losses(recent_trades)
        if stress_type:
            return self._trigger_veto(stress_type, severity, "Consecutive losses detected")

        stress_type, severity = self._check_size_escalation(recent_trades)
        if stress_type:
            return self._trigger_veto(stress_type, severity, "Size escalation detected")

        stress_type, severity = self._check_rapid_trading(recent_trades)
        if stress_type:
            return self._trigger_veto(stress_type, severity, "Excessive trade frequency")

        stress_type, severity = self._check_manual_override_spike(recent_trades)
        if stress_type:
            return self._trigger_veto(stress_type, severity, "Manual override spike")

        stress_type, severity = self._check_hours_anomaly(recent_trades, current_hour)
        if stress_type:
            return self._trigger_veto(stress_type, severity, "Trading at unusual hours")

        stress_type, severity = self._check_chasing_pattern(recent_trades)
        if stress_type:
            return self._trigger_veto(stress_type, severity, "Market chasing pattern")

        return StressAnalysis(
            stress_detected=False,
            stress_type="NORMAL",
            severity=0.0,
            recommendation="ALLOW",
            reason="No stress patterns detected",
            cooldown_minutes=0,
        )

    def _get_recent_trades(self, minutes: int) -> list[TradeRecord]:
        """Get trades from the last N minutes."""
        cutoff = time.time() - (minutes * 60)
        return [t for t in self.trade_history if t.timestamp > cutoff]

    def _check_consecutive_losses(self, trades: list[TradeRecord]) -> tuple[Optional[str], float]:
        """Check for consecutive losses pattern."""
        if self.consecutive_losses >= self.CONSECUTIVE_LOSS_THRESHOLD:
            return "REVENGE_TRADING", min(1.0, self.consecutive_losses * 0.3)
        return None, 0.0

    def _check_size_escalation(self, trades: list[TradeRecord]) -> tuple[Optional[str], float]:
        """Check for increasing position size after losses."""
        if len(trades) < 4:
            return None, 0.0

        sizes = [t.size for t in trades if t.pnl < 0]
        if len(sizes) < 2:
            return None, 0.0

        avg_recent = sum(sizes[-2:]) / 2
        avg_earlier = sum(sizes[:-2]) / max(1, len(sizes) - 2)

        if avg_earlier > 0 and avg_recent / avg_earlier > self.SIZE_INCREASE_THRESHOLD:
            return "SIZE_ESCALATION", 0.7

        return None, 0.0

    def _check_rapid_trading(self, trades: list[TradeRecord]) -> tuple[Optional[str], float]:
        """Check for excessive trade frequency."""
        hour_trades = [t for t in self.trade_history
                      if time.time() - t.timestamp < 3600]

        if len(hour_trades) > self.MAX_TRADES_PER_HOUR:
            return "RAPID_TRADING", min(1.0, len(hour_trades) / self.MAX_TRADES_PER_HOUR)

        return None, 0.0

    def _check_manual_override_spike(self, trades: list[TradeRecord]) -> tuple[Optional[str], float]:
        """Check for increasing manual override frequency."""
        recent_trades = list(self.trade_history)[-20:]

        if len(recent_trades) < 5:
            return None, 0.0

        recent_overrides = sum(1 for t in recent_trades[-5:] if t.manual_override)
        earlier_overrides = sum(1 for t in recent_trades[:-5] if t.manual_override)

        if recent_overrides >= 4 and recent_overrides > earlier_overrides:
            return "MANUAL_OVERRIDE_SPIKE", 0.8

        return None, 0.0

    def _check_hours_anomaly(
        self,
        trades: list[TradeRecord],
        current_hour: int | None = None
    ) -> tuple[Optional[str], float]:
        """Check for trading at unusual hours (emotional state)."""
        if current_hour is None:
            current_hour = time.localtime().tm_hour

        if current_hour < 6 or current_hour > 23:
            return "UNUSUAL_HOURS", 0.5

        return None, 0.0

    def _check_chasing_pattern(self, trades: list[TradeRecord]) -> tuple[Optional[str], float]:
        """Check for 'chasing' the market after losses."""
        if len(trades) < 3:
            return None, 0.0

        loss_trades = [t for t in trades if t.pnl < 0]
        if not loss_trades:
            return None, 0.0

        last_loss_time = loss_trades[-1].timestamp

        trades_after_loss = [t for t in trades if t.timestamp > last_loss_time]

        if len(trades_after_loss) >= 2:
            same_symbol_trades = sum(1 for t in trades_after_loss
                                   if t.symbol == loss_trades[-1].symbol)
            if same_symbol_trades >= 2:
                return "MARKET_CHASING", 0.6

        return None, 0.0

    def _trigger_veto(
        self,
        stress_type: str,
        severity: float,
        reason: str
    ) -> StressAnalysis:
        """Trigger a veto lockout."""
        self.veto_count += 1
        self.last_veto_time = time.time()

        logger.warning(f"STRESS VETO TRIGGERED: {stress_type} (severity: {severity}) - {reason}")

        return StressAnalysis(
            stress_detected=True,
            stress_type=stress_type,
            severity=severity,
            recommendation="LOCKOUT",
            reason=reason,
            cooldown_minutes=self.COOLDOWN_AFTER_VETO,
        )

    def force_cooldown(self, minutes: int = 60):
        """Manually trigger a cooldown period."""
        self.last_veto_time = time.time() - (minutes * 60) + 1

    def get_stats(self) -> dict[str, Any]:
        """Get stress monitoring statistics."""
        return {
            "total_vetos": self.veto_count,
            "consecutive_losses": self.consecutive_losses,
            "total_trades_recorded": len(self.trade_history),
            "veto_active": time.time() - self.last_veto_time < self.COOLDOWN_AFTER_VETO * 60,
        }


_stress_veto_instance: Optional[StressVeto] = None


def get_stress_veto() -> StressVeto:
    """Get the singleton StressVeto instance."""
    global _stress_veto_instance
    if _stress_veto_instance is None:
        _stress_veto_instance = StressVeto()
    return _stress_veto_instance
