"""Live adaptive learning / pattern feedback loop.

The system learns from every closed trade in real time and dynamically adjusts:
- Pattern confidence modifiers based on recent win rate
- Regime permission weights based on regime-specific performance
- Confluence thresholds based on recent market regime quality
- Trade interrogator tolerance based on current streak

This closes the loop between execution outcomes and discovery gates.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveState:
    """Current adaptive adjustments for the system."""

    pattern_confidence_mods: dict[str, float] = field(default_factory=dict)
    regime_permission_mods: dict[str, float] = field(default_factory=dict)
    confluence_threshold: float = 0.70
    interrogator_min_score: float = 0.65
    last_update: float = field(default_factory=time.monotonic)


class PatternFeedbackTracker:
    """Track recent outcomes per pattern and compute rolling modifiers."""

    def __init__(self, lookback: int = 20, min_sample: int = 5) -> None:
        self.lookback = lookback
        self.min_sample = min_sample
        self._trades: dict[str, deque[dict]] = {}

    def record(self, symbol: str, pattern: str, outcome: str, r_multiple: float, regime: str) -> None:
        """Record a trade outcome for a pattern."""
        key = f"{pattern}:{regime}"
        if key not in self._trades:
            self._trades[key] = deque(maxlen=self.lookback)
        self._trades[key].append(
            {
                "symbol": symbol,
                "pattern": pattern,
                "outcome": outcome,
                "r_multiple": r_multiple,
                "regime": regime,
                "timestamp": time.monotonic(),
            }
        )

    def rolling_win_rate(self, pattern: str, regime: str = "ALL") -> float | None:
        """Return rolling win rate for a pattern, optionally scoped to a regime."""
        if regime == "ALL":
            trades = []
            for key, deq in self._trades.items():
                if key.startswith(f"{pattern}:"):
                    trades.extend(deq)
        else:
            trades = list(self._trades.get(f"{pattern}:{regime}", []))

        if len(trades) < self.min_sample:
            return None
        wins = sum(1 for t in trades if t["outcome"] == "WIN")
        return wins / len(trades)

    def confidence_modifier(self, pattern: str, regime: str = "ALL") -> float:
        """Return a confidence modifier in [-0.15, +0.15]."""
        wr = self.rolling_win_rate(pattern, regime)
        if wr is None:
            return 0.0
        if wr >= 0.65:
            return 0.15
        if wr >= 0.50:
            return 0.05
        if wr >= 0.35:
            return -0.05
        return -0.15

    def regime_modifier(self, regime: str) -> float:
        """Return a modifier for regime permission based on all patterns in that regime."""
        trades = []
        for key, deq in self._trades.items():
            if key.endswith(f":{regime}"):
                trades.extend(deq)
        if len(trades) < self.min_sample:
            return 0.0
        wins = sum(1 for t in trades if t["outcome"] == "WIN")
        wr = wins / len(trades)
        if wr >= 0.60:
            return 0.10
        if wr >= 0.45:
            return 0.0
        return -0.10


class LiveAdaptiveEngine:
    """Real-time adaptive learning engine that consumes trade exits and produces adjustments."""

    def __init__(
        self,
        lookback: int = 20,
        min_sample: int = 5,
        base_confluence: float = 0.70,
        base_interrogator: float = 0.65,
    ) -> None:
        self.feedback = PatternFeedbackTracker(lookback=lookback, min_sample=min_sample)
        self.base_confluence = base_confluence
        self.base_interrogator = base_interrogator
        self._state = AdaptiveState(
            confluence_threshold=base_confluence,
            interrogator_min_score=base_interrogator,
        )
        self._last_recompute = 0.0
        self._recompute_interval = 30.0  # seconds

    def ingest_trade_exit(self, payload: dict[str, Any]) -> None:
        """Ingest a trade.exit event payload."""
        symbol = payload.get("symbol", "")
        pattern = payload.get("pattern", "UNKNOWN")
        outcome = "WIN" if float(payload.get("pnl", 0)) > 0 else "LOSS"
        r_multiple = float(payload.get("r_multiple", 0.0))
        regime = payload.get("regime", "UNKNOWN")
        self.feedback.record(symbol, pattern, outcome, r_multiple, regime)
        logger.debug(
            "AdaptiveEngine ingested trade: %s %s %s R=%.2f regime=%s",
            symbol,
            pattern,
            outcome,
            r_multiple,
            regime,
        )

    def recompute(self, force: bool = False) -> AdaptiveState:
        """Recompute adaptive state. Throttled to once per _recompute_interval unless forced."""
        now = time.monotonic()
        if not force and now - self._last_recompute < self._recompute_interval:
            return self._state
        self._last_recompute = now

        # Build pattern confidence modifiers.
        pattern_mods: dict[str, float] = {}
        for key in self.feedback._trades:
            pattern = key.split(":", 1)[0]
            if pattern not in pattern_mods:
                pattern_mods[pattern] = self.feedback.confidence_modifier(pattern)

        # Build regime permission modifiers.
        regime_mods: dict[str, float] = {}
        for key in self.feedback._trades:
            regime = key.rsplit(":", 1)[-1]
            if regime not in regime_mods:
                regime_mods[regime] = self.feedback.regime_modifier(regime)

        # Adjust confluence threshold based on overall recent quality.
        all_trades = []
        for deq in self.feedback._trades.values():
            all_trades.extend(deq)
        if len(all_trades) >= self.feedback.min_sample:
            wins = sum(1 for t in all_trades if t["outcome"] == "WIN")
            overall_wr = wins / len(all_trades)
            if overall_wr >= 0.60:
                confluence_threshold = max(0.55, self.base_confluence - 0.05)
            elif overall_wr >= 0.45:
                confluence_threshold = self.base_confluence
            else:
                confluence_threshold = min(0.85, self.base_confluence + 0.05)
        else:
            confluence_threshold = self.base_confluence

        # Adjust interrogator tolerance based on streak.
        streak = self._recent_streak(all_trades)
        if streak >= 3:
            interrogator_min_score = max(0.55, self.base_interrogator - 0.05)
        elif streak <= -3:
            interrogator_min_score = min(0.75, self.base_interrogator + 0.05)
        else:
            interrogator_min_score = self.base_interrogator

        self._state = AdaptiveState(
            pattern_confidence_mods=pattern_mods,
            regime_permission_mods=regime_mods,
            confluence_threshold=round(confluence_threshold, 2),
            interrogator_min_score=round(interrogator_min_score, 2),
            last_update=now,
        )
        logger.info(
            "AdaptiveEngine recomputed: %d patterns, %d regimes, conf_threshold=%.2f, int_score=%.2f",
            len(pattern_mods),
            len(regime_mods),
            confluence_threshold,
            interrogator_min_score,
        )
        return self._state

    @staticmethod
    def _recent_streak(trades: list[dict]) -> int:
        """Count recent consecutive wins (positive) or losses (negative)."""
        streak = 0
        for t in reversed(trades):
            if t["outcome"] == "WIN":
                if streak >= 0:
                    streak += 1
                else:
                    break
            else:
                if streak <= 0:
                    streak -= 1
                else:
                    break
        return streak

    def current_state(self) -> AdaptiveState:
        """Return the current adaptive state (recompute if stale)."""
        return self.recompute()

    def adjust_pattern_confidence(self, pattern_name: str, base_confidence: float) -> float:
        """Apply adaptive modifier to a pattern confidence."""
        self.recompute()
        mod = self._state.pattern_confidence_mods.get(pattern_name, 0.0)
        return max(0.0, min(100.0, base_confidence * (1 + mod)))

    def adjust_confluence_threshold(self, base: float | None = None) -> float:
        """Return the current confluence threshold."""
        self.recompute()
        return base if base is not None else self._state.confluence_threshold

    def adjust_interrogator_min_score(self, base: float | None = None) -> float:
        """Return the current interrogator min score."""
        self.recompute()
        return base if base is not None else self._state.interrogator_min_score

    async def run_async(self, bus: Any | None = None) -> None:
        """Subscribe to trade.exit events on a shared intelligence bus."""
        if bus is None:
            return
        try:
            await bus.subscribe("trade.exit", self._on_trade_exit)
            logger.info("AdaptiveEngine subscribed to trade.exit")
        except Exception as exc:
            logger.warning("AdaptiveEngine failed to subscribe to trade.exit: %s", exc)

    async def _on_trade_exit(self, payload: dict[str, Any]) -> None:
        self.ingest_trade_exit(payload)


__all__ = [
    "AdaptiveState",
    "PatternFeedbackTracker",
    "LiveAdaptiveEngine",
]
