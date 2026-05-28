"""
State management primitives extracted from brain.py.

Contains drawdown tracking and consecutive-loss escalation logic
that is independent of the main Brain orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

import pytz

logger = logging.getLogger(__name__)


class DrawdownLevel(Enum):
    NORMAL = "NORMAL"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


@dataclass
class DrawdownLadder:
    """Tracks drawdown state for a specific account type."""

    account_type: str  # 'ibkr' or 'prop'
    peak_equity: float = 0.0
    current_equity: float = 0.0
    level: DrawdownLevel = DrawdownLevel.NORMAL
    cooldown_until: datetime | None = None

    # IBKR thresholds (personal account)
    IBKR_THRESHOLDS = {
        DrawdownLevel.NORMAL: 0.07,
        DrawdownLevel.YELLOW: 0.12,
        DrawdownLevel.ORANGE: 0.18,
        DrawdownLevel.RED: 0.25,
    }

    # Prop firm thresholds (FTMO)
    PROP_THRESHOLDS = {
        DrawdownLevel.NORMAL: 0.03,
        DrawdownLevel.YELLOW: 0.05,
        DrawdownLevel.ORANGE: 0.07,
        DrawdownLevel.RED: 0.09,
    }

    def _get_thresholds(self, peak: float) -> dict:
        """Scale thresholds to account size: tighter for small accounts."""
        base = self.PROP_THRESHOLDS if self.account_type == "prop" else self.IBKR_THRESHOLDS
        # For accounts under $2K, compress RED/ORANGE to prevent catastrophic loss
        if peak < 2000:
            scale = max(0.5, peak / 2000)  # 0.5x at near-zero, 1.0x at $2K
            return {
                DrawdownLevel.NORMAL: base[DrawdownLevel.NORMAL],
                DrawdownLevel.YELLOW: base[DrawdownLevel.YELLOW] * scale,
                DrawdownLevel.ORANGE: base[DrawdownLevel.ORANGE] * scale,
                DrawdownLevel.RED: base[DrawdownLevel.RED] * scale,
            }
        return base

    def update(self, equity: float) -> DrawdownLevel:
        """Update drawdown state and return current level."""
        if self.peak_equity == 0:
            logger.info(f"DrawdownLadder ({self.account_type}): Calibrating peak to ${equity:,.2f}")
            self.peak_equity = equity

        self.current_equity = equity
        self.peak_equity = max(self.peak_equity, equity)

        if self.peak_equity <= 0:
            return DrawdownLevel.NORMAL

        dd_pct = (self.peak_equity - equity) / self.peak_equity
        thresholds = self._get_thresholds(self.peak_equity)

        old_level = self.level

        if dd_pct >= thresholds[DrawdownLevel.RED]:
            self.level = DrawdownLevel.RED
        elif dd_pct >= thresholds[DrawdownLevel.ORANGE]:
            self.level = DrawdownLevel.ORANGE
        elif dd_pct >= thresholds[DrawdownLevel.YELLOW]:
            self.level = DrawdownLevel.YELLOW
        else:
            self.level = DrawdownLevel.NORMAL

        if self.level != old_level:
            logger.warning(
                f"Drawdown ladder [{self.account_type}]: {old_level.name} -> {self.level.name} "
                f"(DD: {dd_pct:.2%}, Peak: ${self.peak_equity:.2f}, Current: ${equity:.2f})"
            )
            from trading_state import TradingStateManager

            if self.level == DrawdownLevel.RED:
                TradingStateManager.halt(f"Drawdown Ladder [{self.account_type}] reached RED-ZONE.")
                # Page the operator immediately — RED is a critical capital preservation event
                try:
                    import asyncio as _asyncio
                    from telegram_alerts import send_telegram_alert as _tg
                    msg = (
                        f"[SOVEREIGN ALERT] DRAWDOWN RED-ZONE [{self.account_type.upper()}]\n"
                        f"Peak: ${self.peak_equity:,.2f} → Current: ${self.current_equity:,.2f}\n"
                        f"DD: {((self.peak_equity - self.current_equity) / max(self.peak_equity, 1)):.2%}\n"
                        f"Trading HALTED. Manual review required."
                    )
                    try:
                        loop = _asyncio.get_running_loop()
                        loop.call_soon_threadsafe(_asyncio.ensure_future, _tg(msg))
                    except RuntimeError:
                        # No running event loop (e.g. called from sync startup validation).
                        logger.warning("Drawdown RED alert queued (no running loop): %s", msg)
                except Exception as _tg_exc:
                    logger.error("Could not send RED drawdown Telegram alert: %s", _tg_exc)
            elif self.level in (DrawdownLevel.YELLOW, DrawdownLevel.ORANGE):
                TradingStateManager.reduce_only(
                    f"Drawdown Ladder [{self.account_type}] escalation: {self.level.name}"
                )
            elif self.level == DrawdownLevel.NORMAL:
                TradingStateManager.activate(
                    f"Drawdown Ladder [{self.account_type}] recovered to NORMAL."
                )

        return self.level

    def get_size_modifier(self) -> float:
        """Return position size modifier based on tapered risk profile."""
        modifiers = {
            DrawdownLevel.NORMAL: 1.0,
            DrawdownLevel.YELLOW: 0.50,  # 50% Reduction
            DrawdownLevel.ORANGE: 0.25,  # 75% Reduction
            DrawdownLevel.RED: 0.10,  # 90% Reduction (Capital Preservation)
            DrawdownLevel.CIRCUIT_BREAKER: 0.0,
        }
        return modifiers.get(self.level, 0.0)

    def is_trading_allowed(self) -> bool:
        """Check if trading is permitted (Overridden for Sovereign Strike)."""
        if self.level == DrawdownLevel.CIRCUIT_BREAKER:
            return False
        # Red/Orange levels no longer block trading—they tighten the filter.
        return True


@dataclass
class ConsecutiveLossTracker:
    """
    Graduated response:
    2 losses -> 50% size reduction
    3 losses -> 25% size + 1h pause
    4 losses -> paper mode
    5+ losses -> paper + audit required
    """

    consecutive_losses: int = 0
    win_streak: int = 0  # Breakthrough compounding tracker
    paper_mode_forced: bool = False
    audit_required: bool = False
    pause_until: datetime | None = None
    last_loss_time: datetime | None = None

    def _apply_time_decay(self) -> None:
        """Automatically recover 1 loss every 4 hours of inactivity."""
        if self.consecutive_losses <= 0 or not self.last_loss_time:
            return

        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_loss_time).total_seconds() / 3600

        # Recover 1 loss for every 4 hours
        recovered = int(elapsed // 4)
        if recovered > 0:
            old_losses = self.consecutive_losses
            self.consecutive_losses = max(0, self.consecutive_losses - recovered)
            if self.consecutive_losses < 4:
                self.paper_mode_forced = False
            if self.consecutive_losses < old_losses:
                logger.info(
                    f" RECOVERY: System regained {recovered} loss units via Time-Decay. "
                    f"Current: {self.consecutive_losses}"
                )
                self.last_loss_time = now - timedelta(
                    hours=(elapsed % 4)
                )  # Reset clock for next unit

    def _check_daily_reset(self) -> None:
        """Hard reset loss streak if it's a new trading day (after 8 AM ET)."""
        tz = pytz.timezone("US/Eastern")
        now = datetime.now(tz)
        # Check if we've crossed the 8 AM ET boundary
        if self.last_loss_time:
            # Convert last_loss_time to ET for comparison
            last_loss_et = self.last_loss_time.astimezone(tz)
            if last_loss_et.date() < now.date() and now.hour >= 8:
                if self.consecutive_losses > 0:
                    logger.info(
                        " MORNING RESET: Clearing previous session's loss streak for a fresh start."
                    )
                    self.consecutive_losses = 0
                    self.win_streak = 0
                    self.paper_mode_forced = False
                    self.audit_required = False
                    self.pause_until = None
                    self.last_loss_time = None

    def record_outcome(self, is_win: bool) -> None:
        """Record a trade outcome and update escalation state."""
        self._apply_time_decay()
        self._check_daily_reset()
        if is_win:
            self.consecutive_losses = 0
            self.win_streak += 1  # Win streak tracking
            self.paper_mode_forced = False
            self.audit_required = False
            self.pause_until = None
            if self.win_streak >= 3:
                logger.info(
                    f" VELOCITY REACHED: {self.win_streak} consecutive wins — "
                    "Compounding Risk Mode Active"
                )
        else:
            self.win_streak = 0
            self.consecutive_losses += 1
            self.last_loss_time = datetime.now(timezone.utc)
            if self.consecutive_losses >= 5:
                self.paper_mode_forced = True
                self.audit_required = True
                logger.critical(
                    f"G1 LEVEL 5: {self.consecutive_losses} consecutive losses — "
                    "PAPER MODE + AUDIT REQUIRED"
                )
            elif self.consecutive_losses >= 4:
                self.paper_mode_forced = True
                logger.error(
                    f"G1 LEVEL 4: {self.consecutive_losses} consecutive losses — FORCED PAPER MODE"
                )
            elif self.consecutive_losses >= 3:
                self.pause_until = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.warning(
                    f"G1 LEVEL 3: {self.consecutive_losses} consecutive losses — "
                    "25% size + 1h pause"
                )
            elif self.consecutive_losses >= 2:
                logger.warning(
                    f"G1 LEVEL 2: {self.consecutive_losses} consecutive losses — 50% size reduction"
                )

    def get_size_modifier(self) -> float:
        """Return position size modifier based on consecutive wins/losses."""
        self._apply_time_decay()
        self._check_daily_reset()

        if self.consecutive_losses >= 4:
            return 0.0  # Paper mode — no real trades
        elif self.consecutive_losses >= 3:
            return 0.25
        elif self.consecutive_losses >= 2:
            return 0.50

        if self.win_streak >= 3:
            # Capped compounding: max 1.15x (15% boost) to prevent runaway sizing.
            # Previously uncapped up to 2.0x — a 5-win streak could double position size
            # beyond the F6 Kelly chain limits, bypassing risk controls.
            multiplier = 1.0 + (min(self.win_streak, 4) - 3) * 0.05
            return min(float(multiplier), 1.15)

        return 1.0

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed (not paused/paper)."""
        if self.paper_mode_forced:
            return False
        pause = self.pause_until
        if pause and datetime.now(timezone.utc) < pause:
            return False
        return True



@dataclass
class MorningBudget:
    """Daily risk budget set by Agent A at 8 AM ET."""

    max_trades: int = 2
    min_catalyst: int = 70
    max_risk_per_trade_pct: float = 0.02
    max_daily_risk_pct: float = 0.04
    regime: str = "UNKNOWN"
    generated_at: datetime | None = None

    def generate(
        self,
        regime: str,
        consecutive_losses: int,
        dd_level: DrawdownLevel,
        breadth_score: float = 50.0,
        fomc_proximity_days: int = 30,
        broker: str = "ibkr",
    ) -> None:
        """Generate morning budget based on current conditions."""
        self.regime = regime
        self.generated_at = datetime.now(timezone.utc)

        # Base config by regime
        regime_config = {
            "BULL": {"max_trades": 20, "min_catalyst": 55, "risk_pct": 0.02},
            "TRENDING": {"max_trades": 15, "min_catalyst": 58, "risk_pct": 0.018},
            "CHOPPY": {"max_trades": 10, "min_catalyst": 58, "risk_pct": 0.015},
            "VOLATILE": {"max_trades": 10, "min_catalyst": 60, "risk_pct": 0.01},
            "BEAR": {"max_trades": 8, "min_catalyst": 58, "risk_pct": 0.005},
        }

        config = regime_config.get(regime, regime_config["CHOPPY"])
        self.max_trades = int(config["max_trades"])
        self.min_catalyst = int(config["min_catalyst"])
        self.max_risk_per_trade_pct = float(config["risk_pct"])

        # Consecutive loss modifier
        if consecutive_losses >= 3:
            self.max_trades = min(self.max_trades, 1)
            self.min_catalyst += 10
        elif consecutive_losses >= 2:
            self.min_catalyst += 5

        # Drawdown modifier
        if dd_level in (DrawdownLevel.ORANGE, DrawdownLevel.RED):
            self.max_trades = 0
        elif dd_level == DrawdownLevel.YELLOW:
            self.max_trades = min(self.max_trades, 1)
            self.min_catalyst += 5

        # FOMC proximity (within 2 days)
        if fomc_proximity_days <= 2:
            self.max_trades = min(self.max_trades, 1)
            self.min_catalyst += 10

        # Low breadth modifier
        if breadth_score < 40:
            self.min_catalyst += 5

        # Broker-specific max trade cap (IBKR paper/live is not FTMO constrained)
        from config import IBKR_MAX_TRADES_PER_DAY
        self.max_trades = min(self.max_trades, IBKR_MAX_TRADES_PER_DAY)

        # Prop firm (MT5/FTMO) hard cap — NEVER exceed 2 trades/day regardless of regime
        if broker.lower() in ("mt5", "prop", "ftmo"):
            from config import MAX_TRADES_PER_DAY
            self.max_trades = min(self.max_trades, MAX_TRADES_PER_DAY)
            logger.info(
                f"MorningBudget: Prop firm cap applied — max_trades clamped to {self.max_trades} "
                f"(FTMO limit: {MAX_TRADES_PER_DAY})"
            )

        logger.info(
            f"Morning Budget: regime={regime} max_trades={self.max_trades} "
            f"min_catalyst={self.min_catalyst} max_risk={self.max_risk_per_trade_pct:.2%}"
        )


class TokenBucketRateLimiter:
    """
    Asynchronous Token Bucket for IBKR 50 msgs/sec limit protection.
    Caps order routing to a safe burst frequency.
    """

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        while True:
            async with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(float(self.capacity), self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate wait time for the next token
            await asyncio.sleep(0.01)
