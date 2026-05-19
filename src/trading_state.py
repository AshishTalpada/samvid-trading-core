"""
src/trading_state.py — Sovereign TradingState Finite State Machine
Sovereign TradingState Finite State Machine.

States:
  ACTIVE   — Normal trading, all orders allowed
  REDUCING — Close-only mode: no new entries, exits allowed
  HALTED   — Emergency: all orders denied except cancel

Wire-in:
  - agent_c_ibkr.validate_order_pre_flight() calls TradingStateManager.allow_order()
  - brain.py checks TradingStateManager.state before firing signals
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger("TradingState")


class TradingState(Enum):
    ACTIVE = "ACTIVE"  # Normal full trading
    REDUCING = "REDUCING"  # Close positions only, no new entries
    HALTED = "HALTED"  # All order submission denied


class TradingStateManager:
    """
    Singleton FSM for global trading state.
    All order submission paths must call allow_order() before transmitting.
    """

    _state: TradingState = TradingState.ACTIVE
    _reason: str = "System startup"

    @classmethod
    def state(cls) -> TradingState:
        return cls._state

    @classmethod
    def is_active(cls) -> bool:
        return cls._state == TradingState.ACTIVE

    @classmethod
    def is_halted(cls) -> bool:
        return cls._state == TradingState.HALTED

    @classmethod
    def is_reducing(cls) -> bool:
        return cls._state == TradingState.REDUCING

    @classmethod
    def allow_order(cls, is_close: bool = False) -> tuple[bool, str]:
        """
        Gate every order submission through this method.

        Parameters
        ----------
        is_close : bool
            Set True for exit/close orders (still allowed in REDUCING mode).

        Returns
        -------
        (allowed: bool, reason: str)
        """
        if cls._state == TradingState.HALTED:
            return False, f"TRADING HALTED: {cls._reason}"

        if cls._state == TradingState.REDUCING and not is_close:
            return False, f"REDUCE-ONLY MODE: New entries blocked. {cls._reason}"

        return True, "PROCEED"

    @classmethod
    def activate(cls, reason: str = "Manual activation") -> None:
        """Restore full trading. Use after a halt/reduce-only period has passed."""
        if cls._state != TradingState.ACTIVE:
            logger.info(f"TradingState: ACTIVE ← {cls._state.value} | Reason: {reason}")
            cls._state = TradingState.ACTIVE
            cls._reason = reason

    @classmethod
    def reduce_only(cls, reason: str) -> None:
        """
        Switch to REDUCING mode: only position-closing orders are allowed.
        Triggered by: daily loss limit approaching, VIX spike, drawdown threshold.
        """
        if cls._state != TradingState.REDUCING:
            logger.warning(f"TradingState: REDUCING ← {cls._state.value} | Reason: {reason}")
            cls._state = TradingState.REDUCING
            cls._reason = reason

    @classmethod
    def halt(cls, reason: str) -> None:
        """
        Full trading halt: zero orders transmitted until manually restored.
        Triggered by: critical drawdown breach, broker disconnection, invariant violation.
        """
        if cls._state != TradingState.HALTED:
            logger.critical(f" TradingState: HALTED ← {cls._state.value} | Reason: {reason}")
            cls._state = TradingState.HALTED
            cls._reason = reason

    @classmethod
    def check_daily_pnl(cls, daily_loss_pct: float, limit_pct: float) -> None:
        """
        Automatically escalate state based on daily P&L.

        - At 75% of daily limit → REDUCING
        - At 100% of daily limit → HALTED
        """
        ratio = daily_loss_pct / max(limit_pct, 1e-10)

        if ratio >= 1.0 and cls._state != TradingState.HALTED:
            cls.halt(f"Daily loss limit breached: {daily_loss_pct:.2%} >= {limit_pct:.2%}")
        elif ratio >= 0.75 and cls._state == TradingState.ACTIVE:
            cls.reduce_only(f"Daily loss at 75% of limit: {daily_loss_pct:.2%}")

    @classmethod
    def check_drawdown(cls, current_dd_pct: float, max_dd_pct: float) -> None:
        """
        Automatically escalate state based on portfolio drawdown.

        - At 80% of max drawdown → REDUCING
        - At 100% of max drawdown → HALTED
        """
        ratio = current_dd_pct / max(max_dd_pct, 1e-10)

        if ratio >= 1.0 and cls._state != TradingState.HALTED:
            cls.halt(f"Max drawdown breached: {current_dd_pct:.2%} >= {max_dd_pct:.2%}")
        elif ratio >= 0.80 and cls._state == TradingState.ACTIVE:
            cls.reduce_only(f"Drawdown at 80% of max: {current_dd_pct:.2%}")

    @classmethod
    def status_str(cls) -> str:
        return f"TradingState={cls._state.value} | Reason='{cls._reason}'"
