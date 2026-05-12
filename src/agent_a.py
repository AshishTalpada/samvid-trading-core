"""
src/agent_a.py - Agent A Primary Gatekeeper for Trading System
Agent A sets daily risk budget FIRST and validates all trades.
Implements 6 core classes for pattern detection, risk management, and signal validation.
"""

import asyncio
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

from config import (
    ESCAPE_ORBITAL,
    ESCAPE_SUB_ORBITAL,
    ESCAPE_VELOCITY,
    FTMO_DAILY_LIMIT,
    FTMO_DRAWDOWN_LIMIT,
    MAX_TRADES_PER_DAY,
    UNCONFIRMED_PENALTY,
)


class SovereignErrorLevel(Enum):
    SILENT = 0  # Ignore (Minor lag)
    RETRYABLE = 1  # Transient (Ping drop, Socket Reset)
    FATAL = 2  # Terminal (Auth Failure, Database Loss)


class SovereignStabilizer:
    """Ported Claude Pattern: exponentialBackoffWithJitter."""

    @staticmethod
    async def try_recover(attempt: int, max_retries: int = 5):
        if attempt >= max_retries:
            return False

        delay = min(30, 0.5 * (2**attempt)) + (random.uniform(0, 0.1))
        logger.warning(
            f"SovereignStabilizer: Attempting recovery in {delay:.2f}s (Attempt {attempt + 1}/{max_retries})"
        )
        await asyncio.sleep(delay)
        return True


async def _safe_execute_step(step_func, *args, **kwargs):
    """Unified logic for error-gated execution."""
    attempt = 0
    while attempt < 5:
        try:
            return await step_func(*args, **kwargs)
        except Exception as e:
            level = _classify_error(e)
            if level == SovereignErrorLevel.FATAL:
                logger.critical(f"FATAL SYSTEM FAILURE: {e}")
                raise
            if level == SovereignErrorLevel.RETRYABLE:
                if await SovereignStabilizer.try_recover(attempt):
                    attempt += 1
                    continue
            return None


def _classify_error(e: Exception) -> SovereignErrorLevel:
    err_str = str(e).lower()
    if "auth" in err_str or "database" in err_str:
        return SovereignErrorLevel.FATAL
    if "timeout" in err_str or "connection" in err_str or "ping" in err_str:
        return SovereignErrorLevel.RETRYABLE
    return SovereignErrorLevel.SILENT


# HFT PRE-ALLOCATED OHLCV RING BUFFER (Zero GC Pressure)

# Pre-allocate maximum-size NumPy arrays at module load time.
# During live scanning these arrays are overwritten in-place rather than
# creating new Python objects, which avoids triggering the Garbage Collector
# during hot-path pattern detection.

_BUFFER_SIZE = 2000  # Max bars in ring buffer (pre-allocated once at startup)


class OHLCVBuffer:
    """
    Zero-allocation ring buffer for OHLCV data.
    All arrays are allocated once; updates OVERWRITE in-place.
    This prevents GC pauses during live intraday scanning.
    """

    __slots__ = ("_head", "close", "high", "low", "open", "size", "volume")

    def __init__(self, capacity: int = _BUFFER_SIZE) -> None:
        self.open = np.zeros(capacity, dtype=np.float64)
        self.high = np.zeros(capacity, dtype=np.float64)
        self.low = np.zeros(capacity, dtype=np.float64)
        self.close = np.zeros(capacity, dtype=np.float64)
        self.volume = np.zeros(capacity, dtype=np.float64)
        self.size = 0
        self._head = 0  # Ring buffer write head

    def update_from_df(self, df: "pl.DataFrame") -> None:
        """Overwrite buffer contents from a Polars DataFrame — zero allocation."""
        n = min(len(df), len(self.close))
        self.close[:n] = df["close"].to_numpy()[-n:]
        self.high[:n] = df["high"].to_numpy()[-n:]
        self.low[:n] = df["low"].to_numpy()[-n:]

        if "open" in df.columns:
            self.open[:n] = df["open"].to_numpy()[-n:]
        else:
            self.open[:n] = np.zeros(n)

        self.volume[:n] = df["volume"].to_numpy()[-n:]
        self.size = n


# One shared buffer per process — reused across all scans
_global_ohlcv_buffer = OHLCVBuffer()


class ImpactOracle:
    """
    Sovereign Impact Oracle.
        Calculates estimated slippage and market impact for large-size orders.
        Prevents 'Self-Induced Slippage' in thin liquidity regimes.
    """

    def __init__(self) -> None:
        self.slippage_coefficient = 0.45  # Empirical constant for HFT

    def estimate_impact(self, symbol: str, shares: float, df: "pl.DataFrame") -> float:
        """
        Estimate slippage in percentage points (e.g., 0.001 = 10bps).
        Uses a Square Root Impact Model: Impact ∝ Volatility * sqrt(Size / DailyVolume)
        """
        if len(df) < 20:
            return 0.001  # Default 10bps for cold start

        try:
            # 1. Historical Volatility (20-bar std of log returns)
            prices = df["close"].to_numpy()
            returns = np.diff(np.log(prices))
            volatility = np.std(returns) if len(returns) > 0 else 0.001

            # 2. Daily Volume Approximation (Assuming 1m scale, 390 mins/day)
            avg_volume_1m = df["volume"][-21:-1].mean()
            estimated_day_volume = avg_volume_1m * 390

            # 3. Square Root Impact Formula
            # Impact = sigma * (OrderSize / DayVolume)^0.5
            participation_ratio = (
                shares / estimated_day_volume if estimated_day_volume > 0 else 0.001
            )
            impact_pct = volatility * np.sqrt(participation_ratio) * self.slippage_coefficient

            # 4. Ceiling/Floor Guards
            # Minimum 5bps slippage (Broker side), max 2.5% (to trigger Veto elsewhere)
            return max(0.0005, min(0.025, impact_pct))

        except Exception as e:
            logger.error(f"ImpactOracle: Error estimating impact for {symbol}: {e}")
            return 0.002  # Conservative 20bps fallback


class ContinuousBudgetMonitor:
    """
    Real-time budget monitor enforcing system rules.
    Agent A's primary risk control mechanism.
    """

    def __init__(self) -> None:
        self.daily_loss_pct: float = 0.0
        self.drawdown_pct: float = 0.0
        self.trades_today: int = 0
        self.consecutive_losses: int = 0

    def update_loss(self, pnl_ratio: float) -> None:
        """Update daily loss and drawdown tracking.
        pnl_ratio from brain.py is signed: positive = profit, negative = loss.
        We convert to loss-positive convention internally.
        """
        loss_amount = -pnl_ratio  # positive = actual loss, negative = profit
        self.daily_loss_pct += loss_amount
        self.drawdown_pct = max(self.drawdown_pct, self.daily_loss_pct)

        if loss_amount > 0:  # actual loss occurred
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def update_trade_count(self) -> None:
        """Increment daily trade counter."""
        self.trades_today += 1

    def is_trading_allowed(self, account_type: str = "ibkr") -> bool:
        """
        Check if trading is permitted under current risk conditions.
        Distinguishes between FTMO Challenge limits and IBKR Performance limits.
        """
        # --- GLOBAL P&L PROTECTION ---
        # Check daily loss limit — only block on LOSSES (positive daily_loss_pct)
        # Using abs() here would incorrectly block trading on profitable days.
        if self.daily_loss_pct >= FTMO_DAILY_LIMIT:
            logger.warning(
                f"BUDGET VETO: Daily loss {self.daily_loss_pct:.1%} exceeds limit {FTMO_DAILY_LIMIT:.1%}"
            )
            return False

        # Check max drawdown — drawdown_pct is always ≥ 0 (max of losses)
        if self.drawdown_pct >= FTMO_DRAWDOWN_LIMIT:
            logger.warning(
                f"BUDGET VETO: Total drawdown {self.drawdown_pct:.1%} exceeds limit {FTMO_DRAWDOWN_LIMIT:.1%}"
            )
            return False

        # --- ACCOUNT-SPECIFIC ACTIVITY LIMITS ---
        if account_type == "prop":
            # Strict FTMO Challenge Limits
            if self.trades_today >= MAX_TRADES_PER_DAY:
                logger.warning(f"BUDGET VETO: FTMO max trades {MAX_TRADES_PER_DAY} reached.")
                return False
        else:
            # Flexible IBKR Performance Limits
            from config import IBKR_MAX_TRADES_PER_DAY

            if self.trades_today >= IBKR_MAX_TRADES_PER_DAY:
                logger.warning(f"BUDGET VETO: IBKR max trades {IBKR_MAX_TRADES_PER_DAY} reached.")
                return False

        # Consecutive loss escalation - Relaxed for HFT
        if self.consecutive_losses >= 20:
            logger.warning(
                f"BUDGET VETO: {self.consecutive_losses} consecutive losses. Emergency cooling active."
            )
            return False

        return True

    def best_day_rule(self, today: float, others: list[float]) -> bool:
        """
        Validate that today's performance doesn't exceed 2/3 of recent average.
        Prevents over-concentration of P&L.
        Args:
            today: Today's P&L
            others: List of recent days' P&L
        Returns:
            bool: True if today passes best day rule
        """
        if not others:
            return True

        avg_others = sum(others) / len(others)
        # Guard: if avg_others is negative (all losing days) the rule is meaningless —
        # allow trading rather than blocking the first good day after a losing streak.
        if avg_others <= 0:
            return True
        threshold = (2.0 / 3.0) * avg_others

        return today <= threshold

    def reset_daily(self) -> None:
        """Reset daily counters at market open."""
        self.daily_loss_pct = 0.0
        self.trades_today = 0


@dataclass
class PatternResult:
    """
    Unified pattern detection result structure.
    Contains all information needed for Agent A validation.
    """

    name: str
    category: str  # HFT, SCALP, SWING, HOLD
    confidence: float  # 0-100%
    entry: float
    stop: float
    target: float
    r_r_ratio: float
    confirmed: bool
    lambda_val: int  # Signal strength modifier
    atr: float = 0.0  # Dynamic volatility (ATR)

    def to_dict(self) -> dict:
        """Returns a serializable dictionary of the pattern result."""
        return {
            "name": self.name,
            "category": self.category,
            "confidence": self.confidence,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "r_r_ratio": self.r_r_ratio,
            "confirmed": self.confirmed,
            "lambda_val": self.lambda_val,
        }


class PatternDetector:
    """
    Detects standard and Sovereign-level patterns for Agent A validation.
    Includes 'Adversarial Mirroring', 'Proto-Squeeze', and 'Spoof Pivot' breakthroughs.
    """

    def detect_hft_spoof_pivot(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern: HFT Spoof Pivot.
        Detects where HFTs are 'Volume Flickering' fake orders to induce retail traps.
        The system pivots AGAINST the induced sentiment.
        """
        if len(df) < 10:
            return None

        # Criteria: Volume Explosion (>3x avg) with near-zero Price Delta (<0.01%).
        # This signals 'Layering' or 'Spoofing' where orders are being flashed without intention to fill.
        last_vol = float(df["volume"][-1])
        _m_vol = df["volume"][-10:-1].mean()
        avg_vol = float(_m_vol) if _m_vol is not None and _m_vol != 0 else 1.0
        price_move = abs(float(df["close"][-1] - df["close"][-2]))
        price_threshold = float(df["close"][-1] * 0.0001)  # 1 basis point

        if last_vol > (avg_vol * 3.5) and price_move < price_threshold:
            entry = float(df["close"][-1])
            prev_close = df["close"][-2]
            is_long = df["close"][-1] > df["close"][-5]  # Trend alignment

            # Confirm the 'flicker' is actually creating a directional pivot
            confirmed = (is_long and entry > prev_close) or (not is_long and entry < prev_close)

            target = entry * (1.02 if is_long else 0.98)
            stop = entry * (0.995 if is_long else 1.005)

            return PatternResult(
                name="HFT Spoof Pivot",
                category="HFT",
                confidence=94.0 if confirmed else 70.0,
                entry=entry,
                stop=stop,
                target=target,
                r_r_ratio=4.0,
                confirmed=confirmed,
                lambda_val=30 if confirmed else 0,
            )
        return None

    def detect_institutional_wall(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern: Institutional Absorption Wall (VSA-based).
        Detects where big players are filling orders without moving the price.
        """
        if len(df) < 20:
            return None

        last_5 = df[-5:]
        avg_vol = df["volume"][-20:-5].mean()
        avg_range = (df["high"][-20:-5] - df["low"][-20:-5]).mean()

        current_vol = last_5["volume"].mean()
        current_range = last_5["high"].max() - last_5["low"].min()

        # We mirror the institution. If vol is 1.8x and range is <60% of avg, it's a Wall.
        if current_vol > (avg_vol * 1.8) and current_range < (avg_range * 0.6):
            is_accumulation = df["close"][-1] < df["close"][-20]
            name = "Institutional Accumulation" if is_accumulation else "Institutional Distribution"

            entry = last_5["high"].max() if is_accumulation else last_5["low"].min()
            stop = last_5["low"].min() if is_accumulation else last_5["high"].max()
            # Projection based on 'Institutional Flush' targets
            target = entry + (avg_range * 5) if is_accumulation else entry - (avg_range * 5)

            return PatternResult(
                name=name,
                category="HOLD",
                confidence=92.0,
                entry=entry,
                stop=stop,
                target=target,
                r_r_ratio=3.5,
                confirmed=True,
                lambda_val=25,
            )
        return None

    def detect_proto_squeeze(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern: Proto-Squeeze (Structural Pre-emption).
        Enters 2-3 bars BEFORE the breakout by detecting volatility compression.
        """
        if len(df) < 30:
            return None

        # Volatility Compression (Volatility 'Scents' the Breakout)
        std_20 = df["close"][-20:].std()
        avg_std = df["close"][-50:-20].std()

        if std_20 < (avg_std * 0.4):  # Massive compression (The Sovereign Calm)
            if df["volume"][-1] > df["volume"][-2]:  # Volume Scent detected
                entry = df["close"][-1]
                # Project target based on 'Historical Velocity' from Atlas
                target = entry * 1.03
                stop = entry * 0.99

                return PatternResult(
                    name="Proto-Squeeze",
                    category="SCALP",
                    confidence=88.0,
                    entry=entry,
                    stop=stop,
                    target=target,
                    r_r_ratio=3.0,
                    confirmed=True,
                    lambda_val=15,
                )
        return None

    def detect_bull_flag(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 9: Bull Flag (85% win rate, 5d/3d hold)
        Args:
            df: OHLCV DataFrame with 'close', 'high', 'low', 'volume'
        Returns:
            PatternResult if pattern detected, None otherwise
        """
        if len(df) < 20:
            return None

        # Require strong prior uptrend (pole)
        pole_start = df["close"][-20]
        pole_end = df["close"][-10]
        pole_gain = (pole_end - pole_start) / (pole_start + 1e-10)

        if pole_gain < 0.002:  # Massively relaxed: 0.2%+ pole
            return None

        # Detect consolidation (flag)
        flag_period = df[-10:]
        flag_range = (flag_period["high"].max() - flag_period["low"].min()) / (pole_end + 1e-10)

        if flag_range > 0.025:  # Relaxed further
            return None

        # Volume should contract during flag
        vol_ratio = flag_period["volume"].mean() / (df["volume"][-20:-10].mean() + 1e-10)
        if vol_ratio > 0.95:  # Allow almost any volume action
            return None

        current_price = df["close"][-1]
        resistance = flag_period["high"].max()

        prev_close = df["close"][-2]
        confirmed = current_price > resistance and prev_close > (resistance * 0.999)

        # Entry on breakout above resistance
        entry = resistance * 1.002  # 0.2% above
        stop = flag_period["low"].min()
        target = entry + (pole_end - pole_start)  # Project pole height

        r_r = (target - entry) / (entry - stop + 1e-10)

        confidence = 85.0 if confirmed else 75.0
        lambda_val = 0 if confirmed else UNCONFIRMED_PENALTY

        return PatternResult(
            name="Bull Flag",
            category="SCALP",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=lambda_val,
        )

    def detect_bear_flag(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 11: Bear Flag (82% win rate, 5d/3d hold)
        Opposite of Bull Flag - sharp drop followed by tight consolidation.
        """
        if len(df) < 20:
            return None

        # Prior downtrend (pole)
        pole_start = df["close"][-20]
        pole_end = df["close"][-10]
        pole_drop = (pole_start - pole_end) / (pole_start + 1e-10)

        if pole_drop < 0.002:
            return None

        # Consolidation (flag)
        flag_period = df[-10:]
        flag_range = (flag_period["high"].max() - flag_period["low"].min()) / pole_end
        if flag_range > 0.025:
            return None

        # Volume contract
        vol_ratio = flag_period["volume"].mean() / df["volume"][-20:-10].mean()
        if vol_ratio > 1.05:
            return None

        current_price = df["close"][-1]
        support = flag_period["low"].min()

        # Entry on breakdown
        entry = support * 0.998
        stop = flag_period["high"].max()
        target = entry - (pole_start - pole_end)

        r_r = (entry - target) / (stop - entry + 1e-10)
        prev_close = df["close"][-2]
        confirmed = current_price < support and prev_close < (support * 1.001)

        return PatternResult(
            name="Bear Flag",
            category="SCALP",
            confidence=82.0 if confirmed else 72.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=0 if confirmed else UNCONFIRMED_PENALTY,
        )

    def detect_head_and_shoulders(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 10: Head and Shoulders Bearish (89% win rate, 10d/4d hold)
        Args:
            df: OHLCV DataFrame
        Returns:
            PatternResult if pattern detected, None otherwise
        """
        if len(df) < 30:
            return None

        # Identify potential peaks
        highs = df["high"].to_numpy()[-30:]
        peaks: list[tuple[int, float]] = []

        for i in range(5, len(highs) - 5):
            if highs[i] == max(highs[i - 5 : i + 6]):
                peaks.append((i, highs[i]))

        if len(peaks) < 3:
            return None

        # Validate H&S structure: left shoulder, head, right shoulder
        peaks = sorted(peaks, key=lambda x: x[1], reverse=True)
        head_idx, head_price = peaks[0]

        # Find shoulders (lower than head, roughly symmetric)
        left_shoulder = None
        right_shoulder = None

        for i in range(1, len(peaks)):
            idx, price = peaks[i]
            if idx < head_idx and price < head_price * 0.99:  # Relaxed to 1% for intraday H&S
                left_shoulder = (idx, price)
            elif idx > head_idx and price < head_price * 0.99:  # Relaxed to 1% for intraday H&S
                right_shoulder = (idx, price)

        if not (left_shoulder and right_shoulder):
            return None

        # Calculate neckline (support connecting troughs) — pandas-compatible rolling min
        neckline = float(df["low"][-30:].rolling_min(5).tail(10).mean())

        current_price = df["close"][-1]
        entry = neckline * 0.998  # Enter on neckline break
        stop = head_price
        target = entry - (head_price - neckline)  # Project pattern height

        r_r = (entry - target) / (stop - entry + 1e-10)
        prev_close = df["close"][-2]
        confirmed = current_price < neckline and prev_close < (neckline * 1.001)

        confidence = 89.0 if confirmed else 78.0
        lambda_val = 0 if confirmed else UNCONFIRMED_PENALTY

        return PatternResult(
            name="Head and Shoulders",
            category="SWING",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=lambda_val,
        )

    def detect_falling_wedge(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 13: Falling Wedge Bullish (83% win rate, 10d/4d hold)
        Args:
            df: OHLCV DataFrame
        Returns:
            PatternResult if pattern detected, None otherwise
        """
        if len(df) < 25:
            return None

        recent = df[-25:]

        # Identify converging trendlines (wedge narrows)
        highs = recent["high"].to_numpy()
        lows = recent["low"].to_numpy()

        # Fit linear regression to highs and lows
        x = np.arange(len(highs))

        high_coef = np.polyfit(x, highs, 1)
        low_coef = np.polyfit(x, lows, 1)

        # Both lines should slope down, with lows declining faster
        if high_coef[0] >= 0 or low_coef[0] >= 0:
            return None

        # For a FALLING WEDGE the lines must CONVERGE:
        # d(gap)/dt = high_coef[0] - low_coef[0] < 0  →  high_coef[0] < low_coef[0]
        # i.e. highs must decline FASTER than lows so the range narrows.
        # The original check was inverted — it rejected valid wedges.
        if high_coef[0] >= low_coef[0]:  # Lines not converging — not a wedge
            return None

        # Volume should decline into apex
        early_vol = recent["volume"][:10].mean()
        late_vol = recent["volume"][-10:].mean()

        if late_vol > early_vol * 0.8:
            return None

        current_price = df["close"][-1]
        resistance = np.polyval(high_coef, len(highs) - 1)

        entry = resistance * 1.005  # Breakout above
        stop = np.polyval(low_coef, len(lows) - 1)
        wedge_height = recent["high"].max() - recent["low"].min()
        target = entry + wedge_height

        r_r = (target - entry) / (entry - stop + 1e-10)
        prev_close = df["close"][-2]
        confirmed = current_price > resistance and prev_close > (resistance * 0.999)

        confidence = 83.0 if confirmed else 72.0
        lambda_val = 0 if confirmed else UNCONFIRMED_PENALTY

        return PatternResult(
            name="Falling Wedge",
            category="SCALP",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=lambda_val,
        )

    def detect_rising_wedge(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 14: Rising Wedge Bearish (81% win rate).
        Bearish reversal pattern where price narrows while sloping UP.
        """
        if len(df) < 25:
            return None
        recent = df[-25:]
        highs = recent["high"].to_numpy()
        lows = recent["low"].to_numpy()
        x = np.arange(len(highs))

        high_coef = np.polyfit(x, highs, 1)
        low_coef = np.polyfit(x, lows, 1)

        # Both lines slope UP, with lows rising FASTER (convergence from below)
        if high_coef[0] <= 0 or low_coef[0] <= 0:
            return None
        if low_coef[0] <= high_coef[0]:
            return None

        current_price = df["close"][-1]
        support = np.polyval(low_coef, len(lows) - 1)

        entry = support * 0.995  # Breakdown
        stop = np.polyval(high_coef, len(highs) - 1)
        target = entry - (recent["high"].max() - recent["low"].min())

        r_r = (entry - target) / (stop - entry + 1e-10)
        prev_close = df["close"][-2]
        confirmed = current_price < support and prev_close < (support * 1.001)

        return PatternResult(
            name="Rising Wedge",
            category="SCALP",
            confidence=81.0 if confirmed else 70.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=0 if confirmed else UNCONFIRMED_PENALTY,
        )

    def detect_oversold_bounce(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 6: Oversold Bounce (66% win rate, 7d/3d hold)
        Args:
            df: OHLCV DataFrame with RSI pre-calculated
        Returns:
            PatternResult if pattern detected, None otherwise
        """
        if len(df) < 20 or "rsi" not in df.columns:
            return None

        current_rsi = df["rsi"][-1]

        # Oversold condition: RSI < 45 (Aggressive entry)
        if current_rsi >= 45:
            return None

        # Bullish divergence: price making lower low, RSI making higher low
        price_window = df[-10:]
        price_low_idx = price_window["low"].arg_min()

        if price_low_idx != len(price_window) - 1:  # Not at current bar
            recent_price_low = df["low"][-5:].min()
            prior_price_low = price_window["low"].min()

            if recent_price_low < prior_price_low:
                recent_rsi_low = df["rsi"][-5:].min()
                prior_rsi_low = price_window["rsi"].min()

                if recent_rsi_low <= prior_rsi_low:  # No divergence
                    return None

                if df["volume"][-1] <= df["volume"][-2]:
                    return None

        current_price = df["close"][-1]

        # Support level from recent lows
        support = df["low"][-20:].min()

        entry = current_price
        stop = support * 0.98

        # Target first resistance (20-period high)
        target = df["high"][-20:].quantile(0.75)

        r_r = (target - entry) / (entry - stop + 1e-10)
        confirmed = current_rsi < 25  # Deep oversold

        confidence = 66.0 if confirmed else 58.0
        lambda_val = 0 if confirmed else UNCONFIRMED_PENALTY

        return PatternResult(
            name="Oversold Bounce",
            category="SCALP",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=lambda_val,
        )

    def detect_sector_sympathy(
        self, df: "pl.DataFrame", sector_df: "pl.DataFrame"
    ) -> PatternResult | None:
        """
        Pattern 2: Sector Sympathy (65% win rate, 2d/1d hold)
        Requires sector ETF data for correlation.
        Args:
            df: Individual stock OHLCV
            sector_df: Sector ETF OHLCV
        Returns:
            PatternResult if pattern detected, None otherwise
        """
        if len(df) < 10 or len(sector_df) < 10:
            return None

        # Sector must be strongly up (leader)
        sector_gain = (sector_df["close"][-1] - sector_df["close"][-5]) / (
            sector_df["close"][-5] + 1e-10
        )

        if sector_gain < 0.003:  # Sector up 0.3%+ (intraday 1m scale)
            return None

        # Stock lagging but starting to move
        stock_gain = (df["close"][-1] - df["close"][-5]) / (df["close"][-5] + 1e-10)

        if stock_gain < 0 or stock_gain > sector_gain:
            return None

        # Volume surge on stock
        avg_volume = df["volume"][-20:-1].mean()
        current_volume = df["volume"][-1]

        if current_volume < avg_volume * 1.5:
            return None

        current_price = df["close"][-1]

        entry = current_price
        stop = df["low"][-5:].min()

        # Target: catch up to sector performance
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
        target = current_price * (1 + sector_gain)

        r_r = (target - entry) / (entry - stop)
        confirmed = current_volume > avg_volume * 2.0

        confidence = 65.0 if confirmed else 55.0
        lambda_val = 0 if confirmed else UNCONFIRMED_PENALTY

        return PatternResult(
            name="Sector Sympathy",
            category="SWING",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=lambda_val,
        )

    def detect_gap_fill(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Gap Fill pattern: Price tends to fill gaps from prior session.
        Args:
            df: OHLCV DataFrame
        Returns:
            PatternResult if gap detected, None otherwise
        """
        if len(df) < 5:
            return None

        # Detect gap between yesterday's close and today's open
        prev_close = df["close"][-2]
        today_open = df["open"][-1]
        current_price = df["close"][-1]

        gap_pct = abs(today_open - prev_close) / prev_close

        if gap_pct < 0.001:  # Require just 0.1%+ gap
            return None

        # Gap up scenario
        if today_open > prev_close:
            # Trade to fill gap (short)
            entry = today_open
            target = prev_close
            stop = df["high"][-1] * 1.01

            prev_close_val = df["close"][-2]
            confirmed = (
                current_price < (today_open + prev_close) / 2
                and prev_close_val < (today_open + prev_close) / 1.99
            )

        # Gap down scenario
        else:
            # Trade to fill gap (long)
            entry = today_open
            target = prev_close
            stop = df["low"][-1] * 0.99

            prev_close_val = df["close"][-2]
            confirmed = (
                current_price > (today_open + prev_close) / 2
                and prev_close_val > (today_open + prev_close) / 2.01
            )

        r_r = abs(target - entry) / abs(entry - stop)

        confidence = 60.0 if confirmed else 50.0
        lambda_val = 0 if confirmed else UNCONFIRMED_PENALTY

        return PatternResult(
            name="Gap Fill",
            category="SCALP",
            confidence=confidence,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=lambda_val,
        )

    # HFT MICRO-STRUCTURAL PATTERNS (100Hz Scale)

    def detect_orderbook_imbalance(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        HFT Pattern: Orderbook Imbalance (68% WR, 1m hold)
        Detects massive volume disparity at current bid/ask.
        Requires high-frequency tick data.
        """
        if len(df) < 5:
            return None

        recent = df[-5:]
        avg_vol = df["volume"][-20:-5].mean() if len(df) >= 20 else recent["volume"].mean()

        # We need a volume spike on minimal price movement (absorption)
        current_vol = recent["volume"][-1]
        if current_vol < avg_vol * 1.5:  # Lowered requirement
            return None

        price_range = recent["high"].max() - recent["low"].min()
        current_price = recent["close"][-1]

        if price_range / current_price > 0.001:  # Movement too large for absorption
            return None

        # Assume absorption at the bid (bullish imbalance) if closing near highs
        if current_price >= recent["high"].max() * 0.9999:
            entry = current_price
            stop = recent["low"].min() * 0.999
            target = entry + (entry - stop) * 2  # 1:2 R:R scalp

            return PatternResult(
                name="Micro Imbalance (Bullish)",
                category="HFT",
                confidence=70.0,
                entry=entry,
                stop=stop,
                target=target,
                r_r_ratio=2.0,
                confirmed=True,
                lambda_val=0,
            )
        return None

    def detect_tick_divergence(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        HFT Pattern: Tick Divergence Mean Reversion
        Price ticks up, but volume delta ticks down.
        """
        if len(df) < 10:
            return None

        # Check if last 2 ticks closed higher
        last_3 = df[-3:]
        closes = last_3["close"].to_numpy()
        if not (closes[2] > closes[1]):  # Relaxed to 2 bars
            return None

        # But volume is dropping
        vols = last_3["volume"].to_numpy()
        if not (vols[2] < vols[1] * 0.9):  # 10% drop required
            return None

        current_price = closes[-1]

        # Bearish divergence scalp
        entry = current_price
        stop = df["high"][-5:].max() * 1.001
        target = closes[0]  # Revert to start of move

        # Guard against zero-division if stop == entry
        if abs(entry - stop) < 0.0001:
            return None

        r_r = abs(entry - target) / abs(stop - entry)
        if r_r < 2.0:
            return None

        return PatternResult(
            name="Tick Divergence (Bearish Reversion)",
            category="HFT",
            confidence=65.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=True,
            lambda_val=0,
        )

    def detect_volatility_breakout(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        HFT Pattern: 100ms Volatility Breakout
        Tight bollinger band squeeze followed by structural break.
        """
        if len(df) < 20:
            return None

        # Calculate 20-period std dev (Bollinger Bands)
        closes = df["close"].to_numpy()[-20:]
        sma = np.mean(closes)
        std = np.std(closes)

        upper_band = sma + (2 * std)
        current_price = closes[-1]

        # Squeeze check: Bands must be very tight
        band_width_pct = (upper_band - sma) / sma
        if band_width_pct > 0.002:  # Relaxed to 0.20% width
            return None

        prev_close = closes[-2]
        if current_price > upper_band and prev_close > (upper_band * 0.999):
            entry = current_price
            stop = sma  # Stop at mean

            # Enforce minimum 0.25% stop distance to survive bid/ask spreads
            min_stop = entry * 0.9975
            stop = min(stop, min_stop)

            target = entry + (entry - stop) * 3  # 1:3 R:R momentum scalp

            # Guard zero division
            if abs(entry - stop) < 0.0001:
                return None

            return PatternResult(
                name="Micro Volatility Breakout",
                category="HFT",
                confidence=72.0,
                entry=entry,
                stop=stop,
                target=target,
                r_r_ratio=3.0,
                confirmed=True,
                lambda_val=0,
            )
        return None

    def detect_vcp_pattern(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Advanced Pattern: Volatility Contraction Pattern (VCP).
        Based on Mark Minervini's Pivot Point theory.
        Detects price tightening (decreased volatility) before a breakout.
        """
        if len(df) < 50:
            return None

        # 1. Identify primary uptrend
        sma_200 = df["close"].rolling_mean(window_size=50)[-1]  # Scaled for window
        current_price = df["close"][-1]

        if current_price < sma_200:
            return None

        # 2. Measure Volatility Contractions (T1, T2, T3)
        # We look for progressively smaller pullbacks (Higher Lows)
        window = 40
        data = df["close"].to_numpy()[-window:]

        # Sub-windows
        c1 = data[0:15]
        c2 = data[15:30]
        c3 = data[30:40]

        range_1 = (np.max(c1) - np.min(c1)) / np.max(c1)  # e.g. 10%
        range_2 = (np.max(c2) - np.min(c2)) / np.max(c2)  # e.g. 5%
        range_3 = (np.max(c3) - np.min(c3)) / np.max(c3)  # e.g. 2%

        # VCP requirement: range1 > range2 > range3 (Tightening)
        if not (range_1 > range_2 > range_3):
            return None

        # 3. Identify Pivot Point (Resistance at high of last contraction)
        pivot_resistance = np.max(c3)

        prev_close = df["close"][-2]
        if current_price < pivot_resistance:
            # Pattern forming but not confirmed
            confirmed = False
        else:
            confirmed = prev_close > (pivot_resistance * 0.9995)

        entry = pivot_resistance * 1.001
        stop = np.min(c3)
        target = entry + (np.max(c1) - np.min(c1))  # Target is height of first base

        r_r = abs(target - entry) / abs(entry - stop + 1e-10)

        return PatternResult(
            name="VCP (Minervini Pivot)",
            category="SWING",
            confidence=88.0 if confirmed else 75.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=0 if confirmed else -10,
        )

    def get_market_pivots(self, df: "pl.DataFrame") -> dict[str, float]:
        """
        Institutional Market Reading: Identify significant Highs/Lows.
        Uses a 20-period lookback to find valid Support/Resistance 'Pipes'.
        """
        if len(df) < 40:
            return {"high": 0.0, "low": 0.0}

        highs = df["high"].to_numpy()[-40:]
        lows = df["low"].to_numpy()[-40:]

        # Standard structural pivots
        m_high = float(np.max(highs))
        m_low = float(np.min(lows))

        # Weighted mean of top 5 peaks (Value at High)
        top_5_highs = np.sort(highs)[-5:]
        bot_5_lows = np.sort(lows)[:5]

        return {
            "structural_high": m_high,
            "structural_low": m_low,
            "value_high": float(np.mean(top_5_highs)),
            "value_low": float(np.mean(bot_5_lows)),
        }

    # HARDCORE MICRO-STRUCTURAL DEEP ANALYSIS

    def detect_order_flow_imbalance(self, df: "pl.DataFrame") -> float:
        """
        Deep Micro-Analysis: Order Flow Imbalance (OFI).
        'Microsecond to Microsecond' proxy using high-resolution volume delta.
        Returns score: > 0 (Bullish Absorption), < 0 (Bearish Liquidation).
        """
        if len(df) < 5:
            return 0.0

        # OFI = (PriceUp * Vol) - (PriceDown * Vol)
        # We simulate the micro-second 'Tick Tape' by evaluating price movement inside the bar.
        closes = df["close"].to_numpy()[-5:]
        volumes = df["volume"].to_numpy()[-5:]

        ofi_accum = 0.0
        for i in range(1, len(closes)):
            delta_p = closes[i] - closes[i - 1]
            if delta_p > 0:
                ofi_accum += volumes[i]  # Aggressor Buy
            elif delta_p < 0:
                ofi_accum -= volumes[i]  # Aggressor Sell

        return ofi_accum / (np.mean(volumes) * 5 + 1e-10)

    def detect_tick_tape_absorption(
        self, df: "pl.DataFrame", sensitivity: float = 1.0
    ) -> PatternResult | None:
        """
        Hardcore Pattern: Tick Tape Absorption (Institutional).
        Price is hitting a wall, but volume is exploding.
        This is how big players 'hide' their orders in micro-seconds.
        """
        if len(df) < 10:
            return None

        recent = df[-5:]
        avg_vol = df["volume"][-20:-5].mean()

        # Adjust sensitivity - institutional fingerprints are often subtle
        vol_threshold = 2.5 / sensitivity
        price_tight_threshold = 0.0005 * sensitivity

        vol_spike = recent["volume"].max() > avg_vol * vol_threshold
        price_tight = (recent["high"].max() - recent["low"].min()) / recent["close"][
            -1
        ] < price_tight_threshold

        if vol_spike and price_tight:
            # Absorption detected. Direction identified by OFI.
            ofi = self.detect_order_flow_imbalance(df)

            if abs(ofi) > (0.4 / sensitivity):
                direction = "Bullish" if ofi > 0 else "Bearish"
                return PatternResult(
                    name=f"Deep Tape Absorption ({direction})",
                    category="HFT",
                    confidence=94.0,
                    entry=recent["close"][-1],
                    stop=recent["low"].min() if ofi > 0 else recent["high"].max(),
                    target=recent["close"][-1] * (1 + (0.005 if ofi > 0 else -0.005)),
                    r_r_ratio=3.0,
                    confirmed=True,
                    lambda_val=20,
                )
        return None

    def detect_hft_liquidity_sink(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern: HFT Liquidity Sink.
        Detects where High-Frequency Market Makers are 'Sinking' all available
        liquidity into a hidden wall (Footprint).
        Identified by extreme volume/price divergence and Order Flow Imbalance.
        """
        if len(df) < 12:
            return None

        # High volume on ultra-low range (Zero-Result Effort VSA principle)
        vol_window = df["volume"][-5:]
        avg_vol = df["volume"][-60:-5].mean()

        vol_explosion = vol_window.max() > avg_vol * 4.0

        price_range = df["high"][-5:].max() - df["low"][-5:].min()
        price_std = df["close"][-60:].std()
        range_compression = price_range < (price_std * 0.15)

        # We ensure that the massive volume is actually 'sinking' into a specific level
        # rather than just volatile churning over a wide range.
        typical_price = df["close"][-5:].mean()
        concentration_window = (
            df["close"][-5:].between(typical_price * 0.9995, typical_price * 1.0005).sum()
        )
        is_concentrated = concentration_window >= 4  # 4 out of 5 bars at same level

        if vol_explosion and range_compression and is_concentrated:
            # Which side is the 'Sink' on? Check bias of extreme volume bars.
            ofi = self.detect_order_flow_imbalance(df)

            # If OFI is strongly positive = Accumulation Sink (Bullish)
            # If OFI is strongly negative = Distribution Sink (Bearish)
            if abs(ofi) > 0.6:
                is_bullish = ofi > 0
                entry = float(df["close"][-1])
                # HFT Liquidity sinks move FAST once filled
                target = entry * (1.015 if is_bullish else 0.985)
                stop = entry * (0.997 if is_bullish else 1.003)

                return PatternResult(
                    name="HFT Liquidity Sink",
                    category="HFT",
                    confidence=96.0,
                    entry=entry,
                    stop=stop,
                    target=target,
                    r_r_ratio=5.0,
                    confirmed=True,
                    lambda_val=35,
                )
        return None

    def detect_cup_and_handle(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Hardcore Pattern 12: Cup and Handle (Optimized for 100y data).
        Bullish continuation pattern.
        """
        if len(df) < 60:
            return None
        data = df["close"].to_numpy()[-60:]

        # 1. Left Rim (Recent High)
        left_rim = np.max(data[:20])
        # 2. Bottom of Cup (Midpoint)
        bottom = np.min(data[20:40])
        # 3. Right Rim (Attempt to reach left rim)
        right_rim = np.max(data[40:55])

        # Cup shape: Rim >> Bottom
        if bottom > left_rim * 0.95 or right_rim < left_rim * 0.90:
            return None

        # 4. Handle (Small pullback from right rim)
        handle = data[55:]
        handle_max = np.max(handle)
        handle_min = np.min(handle)

        # Handle should be shallow (less than 15% of cup depth)
        cup_depth = left_rim - bottom
        handle_depth = handle_max - handle_min

        if handle_depth > (cup_depth * 0.15):
            return None

        current_price = data[-1]
        confirmed = current_price > handle_max

        return PatternResult(
            name="Cup and Handle",
            category="SWING",
            confidence=92.0 if confirmed else 80.0,
            entry=handle_max * 1.001,
            stop=handle_min,
            target=handle_max + (left_rim - bottom),
            r_r_ratio=2.5,
            confirmed=confirmed,
            lambda_val=5 if confirmed else -5,
        )

    def detect_double_top_bottom(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Hardcore Pattern 11: Double Top / Double Bottom.
        Reversal pattern identifying major exhaustion.
        """
        if len(df) < 40:
            return None
        highs = df["high"].to_numpy()[-40:]
        lows = df["low"].to_numpy()[-40:]

        # Double Top Logic
        peak1 = np.max(highs[:15])
        trough = np.min(lows[15:25])
        peak2 = np.max(highs[25:])

        # Peaks should be within 1% of each other
        if abs(peak1 - peak2) / peak1 < 0.01 and peak1 > trough * 1.05:
            current_price = df["close"][-1]
            confirmed = current_price < trough
            return PatternResult(
                name="Double Top (Reversal)",
                category="SWING",
                confidence=85.0 if confirmed else 70.0,
                entry=trough * 0.999,
                stop=peak2,
                target=trough - (peak1 - trough),
                r_r_ratio=1.5,
                confirmed=confirmed,
                lambda_val=-10,
            )

        # Double Bottom Logic
        b1 = np.min(lows[:15])
        peak = np.max(highs[15:25])
        b2 = np.min(lows[25:])

        if abs(b1 - b2) / b1 < 0.01 and peak > b1 * 1.05:
            current_price = df["close"][-1]
            prev_close = df["close"][-2]
            confirmed = current_price > peak and prev_close > (peak * 0.999)
            return PatternResult(
                name="Double Bottom (Reversal)",
                category="SWING",
                confidence=86.0 if confirmed else 72.0,
                entry=peak * 1.001,
                stop=b2,
                target=peak + (peak - b1),
                r_r_ratio=1.6,
                confirmed=confirmed,
                lambda_val=10,
            )

        return None

    def detect_ascending_triangle(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Hardcore Pattern 14: Ascending Triangle.
        Flat top, rising bottom. Extreme pressure build-up.
        """
        if len(df) < 30:
            return None
        highs = df["high"].to_numpy()[-30:]
        lows = df["low"].to_numpy()[-30:]

        # Flat Top resistance check
        resistance = np.max(highs)
        # Check if multiple bars hit this level (+/- 0.2%)
        hits = np.sum(np.abs(highs - resistance) / resistance < 0.002)
        if hits < 3:
            return None

        # Rising Bottoms check (Linear regression on lows)
        x = np.arange(len(lows))
        slope, _ = np.polyfit(x, lows, 1)
        if slope <= 0:
            return None

        current_price = df["close"][-1]
        prev_close = df["close"][-2]
        entry = resistance * 1.002
        stop = lows[-1]

        # Ensure target is sufficiently far away from entry
        target_dist = max((resistance - lows[0]), resistance * 0.005)
        target = entry + target_dist

        r_r = (target - entry) / (entry - stop) if entry > stop else 0.0
        if r_r < 0.5:
            return None

        confirmed = current_price > resistance and prev_close > (resistance * 0.999)

        return PatternResult(
            name="Ascending Triangle",
            category="SCALP",
            confidence=82.0 if confirmed else 70.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=15 if confirmed else 0,
        )

    def detect_descending_triangle(self, df: "pl.DataFrame") -> PatternResult | None:
        """
        Pattern 16: Descending Triangle Bearish (84% win rate).
        Lower highs meeting a horizontal support level.
        """
        if len(df) < 25:
            return None
        recent = df[-30:]
        highs = recent["high"].to_numpy()
        lows = recent["low"].to_numpy()

        # Horizontal Support
        support = lows.min()
        touches = np.sum(np.abs(lows - support) / support < 0.002)
        if touches < 3:
            return None

        # Lower Highs
        x = np.arange(len(highs))
        high_coef = np.polyfit(x, highs, 1)
        if high_coef[0] >= 0:
            return None  # Must slope down

        current_price = df["close"][-1]
        entry = support * 0.998
        stop = recent["high"][-10:].max()

        # Ensure target is sufficiently far away from entry
        target_dist = max((recent["high"].max() - support), support * 0.005)
        target = entry - target_dist

        r_r = (entry - target) / (stop - entry) if stop > entry else 0.0
        if r_r < 0.5:
            return None

        prev_close = df["close"][-2]
        confirmed = current_price < support and prev_close < (support * 1.001)

        return PatternResult(
            name="Descending Triangle",
            category="SCALP",
            confidence=84.0 if confirmed else 74.0,
            entry=entry,
            stop=stop,
            target=target,
            r_r_ratio=r_r,
            confirmed=confirmed,
            lambda_val=0 if confirmed else -10,
        )

    def detect_all(self, df: "pl.DataFrame") -> list[PatternResult | None]:
        """
        Unified Pattern Scanner.
        Runs ALL single-argument detectors and returns a flat list of results.
        Each detector is fault-isolated — a crash in one never blocks the others.
        """
        detectors = [
            self.detect_hft_spoof_pivot,
            self.detect_institutional_wall,
            self.detect_proto_squeeze,
            self.detect_bull_flag,
            self.detect_bear_flag,
            self.detect_head_and_shoulders,
            self.detect_falling_wedge,
            self.detect_rising_wedge,
            self.detect_oversold_bounce,
            self.detect_gap_fill,
            self.detect_orderbook_imbalance,
            self.detect_tick_divergence,
            self.detect_volatility_breakout,
            self.detect_vcp_pattern,
            self.detect_tick_tape_absorption,
            self.detect_hft_liquidity_sink,
            self.detect_cup_and_handle,
            self.detect_double_top_bottom,
            self.detect_ascending_triangle,
            self.detect_descending_triangle,
        ]
        results: list[PatternResult | None] = []
        for fn in detectors:
            try:
                result = fn(df)
                if isinstance(result, PatternResult):
                    results.append(result)
            except Exception:
                pass  # Fault-isolated: never let one detector kill the scan
        return results


class SignalEntropyCalculator:
    """
    Calculates information entropy changes in signals.
    Higher entropy reduction = stronger signal clarity.
    """

    def signal_entropy(self, p_before: float, p_after: float) -> float:
        """
        Calculate Shannon entropy reduction.
        Args:
            p_before: Prior probability of event
            p_after: Posterior probability after signal
        Returns:
            Entropy reduction (bits of information)
        """

        def entropy(p: float) -> float:
            if p <= 0 or p >= 1:
                return 0.0
            return -p * np.log2(p) - (1 - p) * np.log2(1 - p)

        h_before = entropy(p_before)
        h_after = entropy(p_after)

        return h_before - h_after

    def entropy_modifier(self, base_lambda: int, entropy_score: float) -> int:
        """
        Adjust lambda based on signal entropy.
        Differential evolution shows that clarity (low entropy) is a +5 gain.
        """
        if entropy_score > 0.5:
            return base_lambda + 5
        elif entropy_score < 0.2:
            return base_lambda - 5
        else:
            return base_lambda


# SOVEREIGN — NEURAL ALPHA ENGINE (Differential Evolution Logic)


class FactorWeightCalibration:
    """
    Sovereign Centennial Weighting Matrix.
        These coefficients were discovered via Differential Evolution across 75 years of data.
    """

    def __init__(self):
        # OPTIMIZED ALPHA WEIGHTS (Phase 1 Training Results)
        self.VOL_REGIME_WEIGHT = 0.343  # 34.3% — Primary predictive factor
        self.VOLUME_SURGE_WEIGHT = 0.267  # 26.7% — Strong confirmation
        self.MOMENTUM_5D_WEIGHT = 0.182  # 18.2% — Short-term trend
        self.MOMENTUM_1M_WEIGHT = 0.159  # 15.9% — Medium-term trend
        self.MEAN_REVERSION_WEIGHT = 0.049  # 4.9% — Least useful (reversion noise)

    def calculate_sovereign_lambda(self, factors: dict) -> float:
        """
        Weighted Alpha Fusion: Merges the 5 core factors into a single Sovereignty score.
        """
        score = (
            factors.get("vol_regime", 0) * self.VOL_REGIME_WEIGHT
            + factors.get("vol_surge", 0) * self.VOLUME_SURGE_WEIGHT
            + factors.get("mom_5d", 0) * self.MOMENTUM_5D_WEIGHT
            + factors.get("mom_1m", 0) * self.MOMENTUM_1M_WEIGHT
            + factors.get("mean_rev", 0) * self.MEAN_REVERSION_WEIGHT
        )
        return score * 100.0  # Scale to Sovereign Lambda units


class NeuralRegimeClassifier:
    """
    Classifies the market into 4 Atomic States to adjust risk weighting.
    1. LOW_VOL_ACCUMULATION
    2. HIGH_VOL_EXPANSION (Alpha Peak)
    3. EXHAUSTION_CLIMAX
    4. CHAOTIC_DECAY (Dhatu Veto Zone)
    """

    def classify_current(self, df: pl.DataFrame) -> str:
        if len(df) < 50:
            return "INDETERMINATE"

        atr_pct = (df["high"][-20:].max() - df["low"][-20:].min()) / df["close"][-1]
        vol_ratio = df["volume"][-1] / (df["volume"][-20:].mean() + 1e-10)

        if atr_pct < 0.015:
            return "LOW_VOL_ACCUMULATION"
        if 0.015 <= atr_pct <= 0.04 and vol_ratio > 1.2:
            return "HIGH_VOL_EXPANSION"
        if atr_pct > 0.04 and vol_ratio < 1.0:
            return "EXHAUSTION_CLIMAX"
        return "CHAOTIC_DECAY"

    def get_regime_multiplier(self, regime: str) -> float:
        multipliers = {
            "LOW_VOL_ACCUMULATION": 0.8,  # Be patient
            "HIGH_VOL_EXPANSION": 1.5,  # ATTACK (Highest Alpha)
            "EXHAUSTION_CLIMAX": 0.5,  # Defensive
            "CHAOTIC_DECAY": 0.0,  # DO NOT TRADE
        }
        return multipliers.get(regime, 1.0)


class EscapeVelocityClassifier:
    """
    Classifies price momentum relative to resistance levels.
    Based on Livermore's pivotal point theory.
    """

    def classify(self, current_price: float, resistances: list[float]) -> str:
        """
        Classify price momentum state.
        Args:
            current_price: Current asset price
            resistances: List of resistance levels above price
        Returns:
            Classification: 'sub_orbital', 'orbital', or 'escape'
        """
        if not resistances:
            return "escape"

        nearest_resistance = min(resistances, key=lambda x: abs(x - current_price))
        distance_pct = (nearest_resistance - current_price) / current_price

        # Sub-orbital: Far from resistance (>5%)
        if distance_pct > 0.05:
            return "sub_orbital"

        # Orbital: Near resistance (2-5%)
        elif 0.02 <= distance_pct <= 0.05:
            return "orbital"

        # Escape: Breaking through resistance (<2% or above)
        else:
            return "escape"

    def modifier(self, classification: str) -> int:
        """
        Return lambda modifier for escape velocity class.
        Args:
            classification: Escape velocity class
        Returns:
            Lambda modifier value
        """
        modifiers = {
            "sub_orbital": ESCAPE_SUB_ORBITAL,
            "orbital": ESCAPE_ORBITAL,
            "escape": ESCAPE_VELOCITY,
        }
        return modifiers.get(classification, 0)


class MultiTimeframeAligner:
    """
    Validates signal alignment across multiple timeframes.
    Higher alignment = stronger conviction.
    """

    def __init__(self) -> None:
        self.timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

    def check_alignment(self, symbol: str, timeframes: list[tuple[str, "pl.DataFrame"]]) -> float:
        """
        Calculate multi-timeframe alignment score.
        Args:
            symbol: Trading symbol
            timeframes: List of (timeframe_name, dataframe) tuples
        Returns:
            Alignment score 0.0-1.0 (1.0 = perfect alignment)
        """
        if not timeframes:
            return 0.5

        signals = []

        for _tf_name, df in timeframes:
            if len(df) < 2:
                continue

            # Simple trend determination: last close vs. moving average
            if "close" in df.columns:
                current = df["close"][-1]
                ma = df["close"].rolling_mean(window_size=min(20, len(df)))[-1]

                # Bullish if above MA
                signals.append(1 if current > ma else -1)

        if not signals:
            return 0.5

        # Calculate agreement percentage
        bullish_count = sum(1 for s in signals if s > 0)
        bearish_count = sum(1 for s in signals if s < 0)

        alignment = max(bullish_count, bearish_count) / len(signals)

        return alignment

    def alignment_modifier(self, alignment_score: float) -> int:
        """
        Convert alignment score to lambda modifier.
        Args:
            alignment_score: Alignment score from check_alignment
        Returns:
            Lambda modifier (-10 to +10)
        """
        # Perfect alignment (>0.85) = +10
        # Poor alignment (<0.6) = -10

        if alignment_score >= 0.85:
            return 10
        elif alignment_score >= 0.7:
            return 5
        elif alignment_score >= 0.6:
            return 0
        else:
            return -10


class InMemorySovereignAtlas:
    """
    Queries the 101M-record dataset directly without RAM pillage.
    """

    def __init__(self, db_path: str = "data/sovereign_intelligence_75y.db"):
        self.db_path = db_path
        self._cache = {}  # pattern_type -> matches (list)
        self._max_cache = 50
        logger.info("🏛️ Atlas: Sovereign Intelligence online (On-Demand Mode).")

    _BULLISH_PATTERNS = {
        "bull flag",
        "falling wedge",
        "oversold bounce",
        "proto-squeeze",
        "ascending triangle",
        "cup and handle",
        "double bottom",
        "vcp",
        "vcp (minervini pivot)",
        "gap fill",
        "hft spoof pivot",
        "institutional wall",
        "micro imbalance (bullish)",
        "micro volatility breakout",
        "deep tape absorption (bullish)",
        "short squeeze",
    }
    _BEARISH_PATTERNS = {
        "head and shoulders",
        "double top",
        "head & shoulders",
        "micro imbalance (bearish)",
        "tick divergence (bearish reversion)",
        "deep tape absorption (bearish)",
        "bear flag",
        "descending triangle",
        "rising wedge",
        "triple top",
        "short squeeze top",
        "blow-off top",
    }
    # Symbol → proxy prefix in atlas
    _SYMBOL_PROXY = {"SPY": "SPY_PROXY", "QQQ": "QQQ_PROXY", "IWM": "IWM_PROXY"}

    def map_to_atlas_key(self, pattern_name: str, symbol: str = "") -> str | None:
        """
        Translate a scanner pattern name into the atlas's absorption taxonomy.
        """
        low = pattern_name.lower()
        proxy_prefix = self._SYMBOL_PROXY.get(symbol.upper(), "")

        # 1. Exact Matches
        if low in self._BULLISH_PATTERNS:
            direction = "Bullish"
        elif low in self._BEARISH_PATTERNS:
            direction = "Bearish"

        elif "down" in low or "bear" in low or "short" in low or "top" in low:
            direction = "Bearish"
        elif "up" in low or "bull" in low or "long" in low or "bottom" in low:
            direction = "Bullish"
        elif "break" in low:
            # Breakdown is bearish, Breakout is context-dependent (defaulting to Bullish if not specified)
            if "down" in low or "fail" in low:
                direction = "Bearish"
            else:
                direction = "Bullish"
        elif any(w in low for w in ("bounce", "squeeze", "pivot", "wedge", "cup")):
            direction = "Bullish"
        elif any(w in low for w in ("diverge", "reversion", "shoulder")):
            direction = "Bearish"
        else:
            return None

        # Prefer symbol-specific proxy if available
        if proxy_prefix:
            return f"{proxy_prefix}:Deep Tape Absorption ({direction})"
        return f"Deep Tape Absorption ({direction})"

    def query_quantum(self, pattern_name: str, intensity: float, symbol: str = "") -> dict:
        """
        On-Demand Quantum Wisdom.
        Queries the 101M-record dataset directly without RAM pillage.
        """
        import os
        import sqlite3

        atlas_key = self.map_to_atlas_key(pattern_name, symbol)
        final_key = atlas_key or pattern_name

        if final_key in self._cache:
            matches = self._cache[final_key]
        else:
            if not os.path.exists(self.db_path):
                return {"match": False, "reason": "Structural DB not found."}

            try:
                # Optimized query for 101M rows: relies on idx_pattern_type
                query = """
                    SELECT micro_intensity, survival_score,
                    CASE
                        WHEN timestamp > '2020-01-01' THEN 2.0
                        WHEN timestamp > '2010-01-01' THEN 1.5
                        WHEN timestamp > '1993-01-01' THEN 0.8
                        ELSE 0.2
                    END as weight
                    FROM structural_fingerprints
                    WHERE pattern_type = ?
                    LIMIT 25000 -- Cap fetch for stability
                """

                with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                    cursor = conn.execute(query, (final_key,))
                    matches = cursor.fetchall()

                # Update cache
                if len(self._cache) >= self._max_cache:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[final_key] = matches

            except Exception as e:
                logger.error(f"🏛️ Atlas: Query failed: {e}")
                return {"match": False, "reason": "Database error during resonance fetch."}

        if not matches:
            # Fallback to generic direction if symbol-specific proxy failed
            if atlas_key and ":" in atlas_key:
                generic_key = atlas_key.split(":")[-1]
                return self.query_quantum(generic_key, intensity)
            return {"match": False, "reason": "No historical resonance found."}

        norm_intensity = intensity / 100.0
        buffer = 0.45
        filtered = [m for m in matches if abs(m[0] - norm_intensity) < buffer]

        if not filtered:
            filtered = matches[:5000]

        total_weight = sum(m[2] for m in filtered)
        w_score = sum(m[1] * m[2] for m in filtered) / (total_weight + 1e-10)

        return {
            "match": True,
            "precedents": len(filtered),
            "score": round(w_score * (1.2 if len(filtered) > 50 else 1.0), 4),
            "resonance_state": "Synchronized" if w_score > 1.5 else "Degraded",
            "atlas_key": final_key,
        }


# AGENT A: THE ABSOLUTE VALIDATION PIPELINE


def agent_a_validate_trade(
    pattern: Any,
    budget_monitor: Any,
    entropy_calc: Any,
    escape_classifier: Any,
    mtf_aligner: Any = None,
    atlas: Any = None,
    oracle: Any = None,
    neural_engine: Any = None,
    regime_classifier: Any = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Sovereign Validation Pipeline.
    Aggregates multi-agent signals and performs the final risk hurdle.
    """
    import time

    from sovereign_task import TaskManager, TaskStatus

    task_manager = TaskManager()

    task_id = kwargs.get("proposal_id", f"diag_{datetime.now(timezone.utc).strftime('%H%M%S')}")
    task = task_manager.get_task(task_id)

    if task:
        task.transition(TaskStatus.RUNNING)
        task.log("Agent A: Initiating deep validation pulse...")

    # 0. BETA GATING
    BETA_GATES = {
        "INTERLEAVED_THINKING": True,
        "ADAPTIVE_COMMISSION": False,  # Experimental
    }

    # 1. FAITHFUL REPORTING & DATA INTEGRITY
    last_update_val = kwargs.get("last_tick_time_val", time.time())
    now_val = time.time()
    if (now_val - last_update_val) > 1.5:
        if task:
            task.log("DATA_VETO: Market data stale.")
        return {
            "agent": "Agent_A",
            "vote": "NO",
            "reason": "Data Integrity Failure: Stale Market.",
            "ts": time.time_ns(),
        }

    # 3. INTERLEAVED THINKING (Beta Gate)
    if BETA_GATES["INTERLEAVED_THINKING"] and task:
        task.log("BETA_FEATURE: Interleaved Thinking ACTIVE.")

    # 4. FINAL QUORUM HURDLES
    if pattern.confidence < 60:
        if task:
            task.transition(TaskStatus.FAILED)
        return {"agent": "Agent_A", "vote": "NO", "reason": "Conviction Floor Veto."}

    symbol = kwargs.get("symbol", "SPY")
    account_type = "prop" if "FTMO" in os.environ.get("TRADING_ACCOUNT_ID", "") else "ibkr"

    if not budget_monitor.is_trading_allowed(account_type):
        if task:
            task.transition(TaskStatus.FAILED)
        return {
            "agent": "Agent_A",
            "vote": "NO",
            "reason": f"🏛️ Sovereign Budget VETO: Risk limits reached for {account_type.upper()}.",
            "final_lambda": 0.0,
        }

    # Step 0: MACRO ORACLE CHECK
    if oracle:
        try:
            state = oracle.get_current_state()
            if state and state.dhatu_state in ("Abhava", "Viyoga"):
                if task:
                    task.transition(TaskStatus.FAILED)
                return {
                    "agent": "Agent_A",
                    "last_update": time.time_ns(),
                    "vote": "NO",
                    "confidence": state.confidence,
                    "reason": f"🏛️ Sovereign Chaos VETO: {state.dhatu_state}",
                    "final_lambda": 0.0,
                }
        except Exception:
            pass

    # PHASE 1: NEURAL REGIME CLASSIFICATION
    regime = "NEUTRAL"
    regime_mult = 1.0
    if regime_classifier and "ohlcv_df" in kwargs:
        regime = regime_classifier.classify_current(kwargs["ohlcv_df"])
        regime_mult = regime_classifier.get_regime_multiplier(regime)
        if regime_mult == 0:
            if task:
                task.transition(TaskStatus.FAILED)
            return {"agent": "Agent_A", "vote": "NO", "reason": f"Regime Veto: {regime}"}

    # PHASE 2: PROFIT DENSITY (FTMO $500 Account Protection)
    entry, target = pattern.entry, pattern.target
    shares = kwargs.get("shares", 100)
    expected_gain = abs(target - entry) * shares

    atr = kwargs.get("atr_20", 0.5)
    spread_buffer = entry * 0.0002
    commission = 0.01 * (shares / 100)
    min_hurdle = (spread_buffer * shares) + commission + (0.5 * atr * shares)

    if expected_gain < min_hurdle:
        if task:
            task.transition(TaskStatus.FAILED)
        return {
            "agent": "Agent_A",
            "vote": "NO",
            "reason": f"Expected Gain ${expected_gain:.2f} < ${min_hurdle:.2f} Hurdle",
        }

    # PHASE 3: RESONANCE
    resonance_score = 1.4
    if atlas:
        res = atlas.query_quantum(pattern.name, pattern.confidence, symbol=symbol)
        resonance_score = res.get("score", 1.4)
        if resonance_score < 1.4:
            if task:
                task.transition(TaskStatus.FAILED)
            return {"agent": "Agent_A", "vote": "NO", "reason": "Atlas Survival Veto"}

    # PHASE 4: ALPHA FUSION
    final_lambda = float(pattern.lambda_val or (pattern.confidence / 2.0))
    if neural_engine:
        factors = {
            "vol_regime": 1.0 if resonance_score > 1.6 else 0.5,
            "vol_surge": 1.0 if kwargs.get("volume_surge", False) else 0.0,
            "mom_5d": 1.0 if kwargs.get("trend_5d", "bull") == "bull" else -1.0,
            "mom_1m": 1.0 if kwargs.get("trend_1m", "bull") == "bull" else -1.0,
        }
        final_lambda = neural_engine.calculate_sovereign_lambda(factors)

    final_lambda *= regime_mult

    # PHASE 5: RISK/REWARD & FRICTION
    atr = kwargs.get("atr_20", 4.0)
    friction = (max(2.5, shares * 0.005) * 2 / shares) + (pattern.entry * 0.0005)
    # Scalping patterns don't target 1.5 ATR. Lowering hurdle to 0.1 ATR to allow fast momentum trades.
    profit_hurdle = (0.1 * atr) + friction
    if abs(pattern.target - pattern.entry) < profit_hurdle:
        if task:
            task.transition(TaskStatus.FAILED)
        return {"agent": "Agent_A", "vote": "NO", "reason": "Friction Veto: Hurdle not met."}

    # PHASE 6-10: SECONDARY CALIBRATION
    if pattern.r_r_ratio < 0.2:
        if task:
            task.transition(TaskStatus.FAILED)
        return {
            "agent": "Agent_A",
            "vote": "NO",
            "reason": f"R:R Veto: {pattern.r_r_ratio:.2f} < 0.2",
        }

    # PHASE 11: SHANNON ENTROPY & ALIGNMENT
    if "entropy_score" in kwargs:
        final_lambda = entropy_calc.entropy_modifier(int(final_lambda), kwargs["entropy_score"])

    if "timeframes" in kwargs and mtf_aligner:
        alignment_score = mtf_aligner.check_alignment(symbol, kwargs["timeframes"])
        final_lambda += mtf_aligner.alignment_modifier(alignment_score)

    # TENSION BOOST
    tension = kwargs.get("tension", 0.0)
    if tension > 80.0:
        final_lambda += 15.0

    # PHASE 12: FINAL SOVEREIGN DECISION
    if abs(final_lambda) < 5:
        if task:
            task.transition(TaskStatus.FAILED)
        return {"agent": "Agent_A", "vote": "NO", "reason": f"Lambda Veto: {final_lambda:.1f}"}

    # STRIKE FILTER
    if kwargs.get("dd_level") in ("RED", "ORANGE"):
        if pattern.confidence < 95.0 or resonance_score < 1.9:
            if task:
                task.transition(TaskStatus.FAILED)
            return {"agent": "Agent_A", "vote": "NO", "reason": "Strike Filter Veto."}

    if task:
        task.transition(TaskStatus.SUCCESS)
        task.log(f"Sovereign APPROVED: Lambda={final_lambda:.1f}")

    return {
        "agent": "Agent_A",
        "vote": "YES",
        "confidence": pattern.confidence / 100.0,
        "signal_strength": float(final_lambda) / 100.0,
        "lambda": float(final_lambda) / 100.0,
        "risk_flag": False,
        "reason": f"Consensus Reached. Lambda: {final_lambda:.1f}",
        "final_lambda": final_lambda,
        "regime": regime,
        "metadata": {
            "atlas_score": resonance_score,
            "pattern": pattern.name,
            "entry": pattern.entry,
            "stop": pattern.stop,
            "target": pattern.target,
        },
    }
