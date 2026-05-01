"""
src/position_sizer.py — Unified Position Sizing Engine
Replaces scattered implementations in brain.py, backtest_engine.py, agent_c_ibkr.py.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("PositionSizer")


class PositionSizer:
    """Single source of truth for all position sizing logic."""

    @staticmethod
    def fixed_risk(
        equity: float, risk_pct: float, entry: float, stop: float, min_shares: int = 1
    ) -> float:
        """Risk exactly risk_pct of equity on the stop distance."""
        if equity <= 0 or risk_pct <= 0 or entry <= 0:
            return float(min_shares)
        stop_distance = abs(entry - stop)
        if stop_distance < 0.001:
            logger.warning(
                f"PositionSizer: Near-zero stop distance ({stop_distance:.4f}). Min shares."
            )
            return float(min_shares)
        shares = (equity * risk_pct) / stop_distance
        return max(float(min_shares), round(shares, 4))

    @staticmethod
    def kelly(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.25,
        max_pct: float = 0.20,
    ) -> float:
        """Fractional Kelly criterion — returns fraction of equity to allocate."""
        if avg_loss <= 0 or win_rate <= 0:
            return 0.0
        b = avg_win / avg_loss
        k = (b * win_rate - (1.0 - win_rate)) / b
        return min(max(0.0, k * fraction), max_pct)

    @staticmethod
    def percent_equity(equity: float, pct: float, price: float, min_shares: int = 1) -> float:
        """Allocate a fixed % of equity regardless of stop distance."""
        if equity <= 0 or pct <= 0 or price <= 0:
            return float(min_shares)
        return max(float(min_shares), round((equity * pct) / price, 4))

    @staticmethod
    def validate(
        shares: float,
        price: float,
        equity: float,
        max_notional_pct: float = 0.15,
        max_notional_abs: float | None = None,
        min_shares: int = 1,
    ) -> float:
        """Safety cap — never exceed max_notional_pct of equity in a single order."""
        if price <= 0 or equity <= 0:
            return float(min_shares)
        max_by_pct = (equity * max_notional_pct) / price
        if max_notional_abs is not None:
            capped = min(shares, max_by_pct, max_notional_abs / price)
        else:
            capped = min(shares, max_by_pct)
        result = max(float(min_shares), round(capped, 4))
        if result < shares:
            logger.debug(
                f"PositionSizer: Capped {shares:.2f}→{result:.2f} (limit ${result * price:,.0f})"
            )
        return result

    @staticmethod
    def to_whole_shares(shares: float) -> int:
        return max(1, int(shares))

    @classmethod
    def size_trade(
        cls,
        equity: float,
        risk_pct: float,
        entry: float,
        stop: float,
        win_rate: float = 0.5,
        avg_win: float = 0.0,
        avg_loss: float = 0.0,
        max_notional_pct: float = 0.15,
        max_notional_abs: float | None = None,
        use_kelly: bool = False,
    ) -> int:
        """Full pipeline: compute → validate → return whole shares."""
        if use_kelly and avg_win > 0 and avg_loss > 0 and win_rate > 0:
            raw = cls.percent_equity(equity, cls.kelly(win_rate, avg_win, avg_loss), entry)
        else:
            raw = cls.fixed_risk(equity, risk_pct, entry, stop)
        return cls.to_whole_shares(
            cls.validate(raw, entry, equity, max_notional_pct, max_notional_abs)
        )
