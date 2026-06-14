"""
Regime Stops (#164 from SOVEREIGN_ULTIMATE_CHECKLIST).
ATR-based stops that adapt to BULL/BEAR/CHOPPY market regimes.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RegimeStopConfig:
    """Configuration for regime-based stops."""

    bull_multiplier: float = 2.0
    bear_multiplier: float = 1.5
    choppy_multiplier: float = 3.0
    trailing_atr_percent: float = 0.5


class RegimeStopEngine:
    """
    ATR-based adaptive stops that adjust based on market regime.

    BULL: Tighter stops, allow more run
    BEAR: Wider stops to avoid wicks, protect capital
    CHOPPY: Wide stops to avoid noise
    """

    REGIME_THRESHOLDS = {
        "BULL": {"vix_max": 20, "mom_min": 0.01},
        "BEAR": {"vix_min": 30, "mom_max": -0.01},
        "CHOPPY": {"vix_range": (20, 30), "mom_range": (-0.01, 0.01)},
    }

    def __init__(self, config: Optional[RegimeStopConfig] = None):
        self.config = config or RegimeStopConfig()
        self.atr_history: Any = []
        self.last_stop = None

    def calculate_atr(
        self,
        high: list[float],
        low: list[float],
        close: list[float],
        period: int = 14,
    ) -> float:
        """
        Calculate Average True Range.

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period

        Returns:
            ATR value
        """
        if len(high) < period + 1 or len(low) < period + 1 or len(close) < period + 1:
            return 0.0

        highs = np.array(high)
        lows = np.array(low)
        closes = np.array(close)

        high_low = highs[1:] - lows[1:]
        high_close = np.abs(highs[1:] - closes[:-1])
        low_close = np.abs(lows[1:] - closes[:-1])

        true_range = np.maximum(high_low, np.maximum(high_close, low_close))

        atr = np.mean(true_range[-period:])

        self.atr_history.append(atr)
        if len(self.atr_history) > 100:
            self.atr_history.pop(0)

        return float(atr)

    def detect_regime(
        self,
        vix: float,
        momentum: float,
        regime_label: Optional[str] = None,
    ) -> str:
        """
        Detect current market regime.

        Args:
            vix: Current VIX level
            momentum: Current momentum indicator
            regime_label: Optional explicit regime from other systems

        Returns:
            Regime name: BULL, BEAR, or CHOPPY
        """
        if regime_label:
            regime_upper = regime_label.upper()
            if any(r in regime_upper for r in ["BULL", "UP", "VRIDDHI"]):
                return "BULL"
            elif any(r in regime_upper for r in ["BEAR", "DOWN", "KSHAYA"]):
                return "BEAR"

        if (
            vix < self.REGIME_THRESHOLDS["BULL"]["vix_max"]
            and momentum > self.REGIME_THRESHOLDS["BULL"]["mom_min"]
        ):  # type: ignore
            return "BULL"
        elif (
            vix > self.REGIME_THRESHOLDS["BEAR"]["vix_min"]
            or momentum < self.REGIME_THRESHOLDS["BEAR"]["mom_max"]
        ):  # type: ignore
            return "BEAR"
        else:
            return "CHOPPY"

    def calculate_stop(
        self,
        entry_price: float,
        atr: float,
        regime: str,
        position_type: str = "LONG",
    ) -> dict[str, Any]:
        """
        Calculate adaptive stop loss based on regime.

        Args:
            entry_price: Entry price of the position
            atr: Current ATR value
            regime: Detected market regime
            position_type: LONG or SHORT

        Returns:
            Dictionary with stop levels and rationale
        """
        if regime == "BULL":
            multiplier = self.config.bull_multiplier
            stop_distance = atr * multiplier
            stop_type = "TIGHT_BULL"
            rationale = "Bull markets allow tighter stops to capture runs"
        elif regime == "BEAR":
            multiplier = self.config.bear_multiplier
            stop_distance = atr * multiplier
            stop_type = "WIDE_BEAR"
            rationale = "Bear markets require wider stops to survive wicks"
        else:
            multiplier = self.config.choppy_multiplier
            stop_distance = atr * multiplier
            stop_type = "WIDE_CHOPPY"
            rationale = "Choppy markets need wide stops to avoid noise"

        if position_type == "LONG":
            stop_price = entry_price - stop_distance
            break_even = entry_price + (stop_distance * 0.5)
        else:
            stop_price = entry_price + stop_distance
            break_even = entry_price - (stop_distance * 0.5)

        # MARKET-MAKER STOP-HUNT AVOIDANCE
        # If we have enough price history, nudge the stop away from known cluster levels
        try:
            from mm_simulator import MarketMakerSimulator
            mm = MarketMakerSimulator()
            # Build a simple price history around entry for cluster detection
            # Use entry ± 3*stop_distance as a proxy recent range
            prices = [
                entry_price - 3 * stop_distance + (i * 0.05)
                for i in range(int(6 * stop_distance / 0.05))
            ]
            safe_stop = mm.safe_stop_level(
                entry=entry_price,
                side="long" if position_type == "LONG" else "short",
                prices=prices,
                buffer_pct=0.003,
            )
            # Only adjust if the MM-safe level is further from entry (more protective)
            if position_type == "LONG":
                if safe_stop < stop_price:
                    stop_price = safe_stop
                    stop_type = f"{stop_type}_MM_SAFE"
                    rationale += " | MM-safe stop pushed below cluster level."
            else:
                if safe_stop > stop_price:
                    stop_price = safe_stop
                    stop_type = f"{stop_type}_MM_SAFE"
                    rationale += " | MM-safe stop pushed above cluster level."
        except Exception as mm_err:
            import logging
            logging.getLogger(__name__).debug("MM stop adjustment skipped: %s", mm_err)

        self.last_stop = {  # type: ignore
            "entry": entry_price,
            "stop": stop_price,
            "atr": atr,
            "regime": regime,
            "type": stop_type,
        }

        return {
            "entry_price": entry_price,
            "stop_price": stop_price,
            "break_even_price": break_even,
            "atr": atr,
            "atr_multiplier": multiplier,
            "regime": regime,
            "stop_type": stop_type,
            "rationale": rationale,
            # Target is placed at 2x the stop distance, so the planned R:R is constant.
            # (The previous expression (atr*m*2)/(atr*m) was a tautology that also raised
            # ZeroDivisionError when atr == 0.0, which calculate_atr() returns on thin data.)
            "risk_reward_ratio": 2.0,
        }

    def calculate_trailing_stop(
        self,
        current_price: float,
        peak_price: float,
        atr: float,
        regime: str,
        position_type: str = "LONG",
    ) -> float:
        """
        Calculate trailing stop that adjusts with regime.

        Args:
            current_price: Current market price
            peak_price: Highest reached price (for LONG)
            atr: Current ATR
            regime: Current regime
            position_type: LONG or SHORT

        Returns:
            Trailing stop price
        """
        if regime == "BULL":
            trailing_percent = self.config.trailing_atr_percent * 0.5
        elif regime == "BEAR":
            trailing_percent = self.config.trailing_atr_percent * 1.5
        else:
            trailing_percent = self.config.trailing_atr_percent * 2.0

        if position_type == "LONG":
            atr_trailing = atr * trailing_percent
            trailing_stop = peak_price - atr_trailing
        else:
            atr_trailing = atr * trailing_percent
            trailing_stop = peak_price + atr_trailing

        if self.last_stop and position_type == "LONG":
            trailing_stop = max(trailing_stop, self.last_stop["stop"])
        elif self.last_stop and position_type == "SHORT":
            trailing_stop = min(trailing_stop, self.last_stop["stop"])

        return trailing_stop

    def get_regime_recommendation(self, regime: str) -> dict[str, Any]:
        """
        Get trading recommendations based on regime.

        Args:
            regime: Current market regime

        Returns:
            Recommendation dictionary
        """
        if regime == "BULL":
            return {
                "position_sizing": "AGGRESSIVE",
                "stop_distance": "TIGHT",
                "target_multiplier": "3x",
                "time_horizon": "SWING",
                "strategy": "Trend following, let winners run",
            }
        elif regime == "BEAR":
            return {
                "position_sizing": "DEFENSIVE",
                "stop_distance": "WIDE",
                "target_multiplier": "2x",
                "time_horizon": "INTRADAY",
                "strategy": "Short-biased, quick exits, preserve capital",
            }
        else:
            return {
                "position_sizing": "CONSERVATIVE",
                "stop_distance": "WIDE",
                "target_multiplier": "1.5x",
                "time_horizon": "SCALP",
                "strategy": "Range trading, mean reversion, tight stops",
            }


_regime_stop_instance: Optional[RegimeStopEngine] = None


def get_regime_stop_engine() -> RegimeStopEngine:
    """Get the singleton RegimeStopEngine instance."""
    global _regime_stop_instance
    if _regime_stop_instance is None:
        _regime_stop_instance = RegimeStopEngine()
    return _regime_stop_instance
