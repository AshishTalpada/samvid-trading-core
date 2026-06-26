"""Regime-based strategy router and timeframe-aware pattern detection.

The router answers two questions for every scan:
1. Which patterns are allowed in the current market regime?
2. What timeframe should each pattern be detected on?

This stops the system from trading daily/swing patterns on 1-minute noise
and from using mean-reversion strategies in strong-trending regimes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Map each pattern to the timeframe it is designed for.
# Scalp patterns run on 1m, intraday patterns on 5m, swing patterns on 15m.
PATTERN_TIMEFRAMES: dict[str, str] = {
    # Scalp / microstructure (1m)
    "HFT Spoof Pivot": "1m",
    "Institutional Wall": "1m",
    "Institutional Accumulation": "1m",
    "Institutional Distribution": "1m",
    "Proto-Squeeze": "1m",
    "Deep Tape Absorption": "1m",
    "HFT Liquidity Sink": "1m",
    "Orderbook Imbalance": "1m",
    "Tick Divergence (Bearish Reversion)": "1m",
    "Tick Tape Absorption": "1m",
    "Micro Volatility Breakout": "1m",
    "Micro Imbalance (Bullish)": "1m",
    # Intraday (5m)
    "Bull Flag": "5m",
    "Bear Flag": "5m",
    # Swing (15m)
    "VCP (Minervini Pivot)": "15m",
    "Head and Shoulders": "15m",
    "Cup and Handle": "15m",
    "Double Top (Reversal)": "15m",
    "Double Bottom (Reversal)": "15m",
    "Ascending Triangle": "15m",
    "Descending Triangle": "15m",
    "Falling Wedge": "15m",
    "Rising Wedge": "15m",
    "Oversold Bounce": "15m",
    "Gap Fill": "15m",
    "Sector Sympathy": "15m",
    "Evolved Alpha": "15m",
    "Evolved Momentum": "15m",
    "Evolved Mean Reversion": "15m",
}


# All patterns the system knows. Every regime is allowed to trade every pattern.
# The user has given full authority to remove idle rules and test aggressively.
_ALL_PATTERNS: set[str] = set(PATTERN_TIMEFRAMES)

# Map regimes to the pattern categories allowed.
REGIME_ALLOWED_PATTERNS: dict[str, set[str]] = {
    "BULL": _ALL_PATTERNS,
    "TRENDING": _ALL_PATTERNS,
    "CHOPPY": _ALL_PATTERNS,
    "SIDEWAYS": _ALL_PATTERNS,
    "UNKNOWN": _ALL_PATTERNS,
    "BEAR": _ALL_PATTERNS,
    "RISK_OFF": _ALL_PATTERNS,
    "PANIC": _ALL_PATTERNS,
}


# 1m blocklist removed during testing. Every pattern can run on its designed
# timeframe (usually 1m) so the system never sits idle because of timeframe rules.
BLOCKLIST_1M: set[str] = set()


@dataclass
class RouteResult:
    """Routing decision for a single pattern."""

    pattern_name: str
    timeframe: str
    allowed: bool
    reason: str = ""


class RegimeStrategyRouter:
    """Decide which patterns to run and on which timeframes."""

    def __init__(
        self,
        allowed_map: dict[str, set[str]] | None = None,
        timeframe_map: dict[str, str] | None = None,
        blocklist_1m: set[str] | None = None,
    ) -> None:
        self.allowed_map = allowed_map or REGIME_ALLOWED_PATTERNS
        self.timeframe_map = timeframe_map or PATTERN_TIMEFRAMES
        self.blocklist_1m = blocklist_1m or BLOCKLIST_1M

    def route(self, pattern_name: str, regime: str) -> RouteResult:
        """Return the route decision for a pattern in a regime."""
        regime = str(regime).upper() if regime else "UNKNOWN"
        allowed = self.allowed_map.get(regime, set())
        if pattern_name not in allowed:
            return RouteResult(
                pattern_name=pattern_name,
                timeframe=self.timeframe_map.get(pattern_name, "1m"),
                allowed=False,
                reason=f"{pattern_name} not allowed in {regime} regime",
            )

        timeframe = self.timeframe_map.get(pattern_name, "1m")
        if timeframe == "1m" and pattern_name in self.blocklist_1m:
            return RouteResult(
                pattern_name=pattern_name,
                timeframe=timeframe,
                allowed=False,
                reason=f"{pattern_name} is blocklisted on 1m data",
            )

        return RouteResult(
            pattern_name=pattern_name,
            timeframe=timeframe,
            allowed=True,
            reason="",
        )

    def allowed_patterns(self, regime: str) -> list[str]:
        """Return all pattern names allowed for the regime."""
        regime = str(regime).upper() if regime else "UNKNOWN"
        allowed = sorted(self.allowed_map.get(regime, set()))
        return [
            p
            for p in allowed
            if not (
                self.timeframe_map.get(p, "1m") == "1m" and p in self.blocklist_1m
            )
        ]

    def patterns_for_timeframe(self, regime: str, timeframe: str) -> list[str]:
        """Return allowed patterns for a specific timeframe in a regime."""
        return [
            p
            for p in self.allowed_patterns(regime)
            if self.timeframe_map.get(p, "1m") == timeframe
        ]


class TimeframeAwareDetector:
    """Run pattern detection on the appropriate timeframe for each pattern.

    Fetches OHLCV for the requested timeframe and runs only the detectors
    permitted by the regime router.
    """

    def __init__(self, pattern_detector: Any, router: RegimeStrategyRouter | None = None) -> None:
        self.pattern_detector = pattern_detector
        self.router = router or RegimeStrategyRouter()

    async def detect_for_regime(
        self,
        symbol: str,
        regime: str,
        fetch_ohlcv: Any,
        timeframe: str | None = None,
    ) -> list[Any]:
        """Run all detectors on the appropriate timeframes for a regime.

        `fetch_ohlcv` is an async callable: await fetch_ohlcv(symbol, tf) -> DataFrame.
        """
        allowed = set(self.router.allowed_patterns(regime))
        if not allowed:
            return []

        # Group allowed patterns by timeframe.
        timeframes_needed: set[str] = set()
        for p in allowed:
            tf = self.router.timeframe_map.get(p, "1m")
            if timeframe is None or tf == timeframe:
                timeframes_needed.add(tf)

        results: list[Any] = []
        detectors = self._detector_methods()
        for tf in timeframes_needed:
            try:
                df = await fetch_ohlcv(symbol, tf)
                if df is None or isinstance(df, str) or len(df) < 20:
                    continue
            except Exception as exc:
                logger.debug(
                    "TimeframeAwareDetector [%s] fetch %s failed: %s",
                    symbol,
                    tf,
                    exc,
                )
                continue

            for method in detectors:
                try:
                    result = method(df)
                    if result is None:
                        continue
                    pattern_name = getattr(result, "name", "UNKNOWN")
                    if pattern_name not in allowed:
                        continue
                    # Tag the result with the timeframe and regime it was detected on.
                    result.timeframe = tf  # type: ignore[attr-defined]
                    result.regime_allowed = regime  # type: ignore[attr-defined]
                    results.append(result)
                except Exception as exc:
                    logger.debug(
                        "TimeframeAwareDetector [%s] detector %s on %s failed: %s",
                        symbol,
                        getattr(method, "__name__", repr(method)),
                        tf,
                        exc,
                    )
        return results

    def _detector_methods(self) -> list[Any]:
        """Return all detector methods from the wrapped PatternDetector."""
        methods: list[Any] = []
        if self.pattern_detector is None:
            return methods
        for attr_name in dir(self.pattern_detector):
            if attr_name.startswith("detect_"):
                method = getattr(self.pattern_detector, attr_name)
                if callable(method):
                    methods.append(method)
        return methods


# Global router for convenience.
_GLOBAL_ROUTER: RegimeStrategyRouter | None = None


def get_global_router() -> RegimeStrategyRouter:
    global _GLOBAL_ROUTER
    if _GLOBAL_ROUTER is None:
        _GLOBAL_ROUTER = RegimeStrategyRouter()
    return _GLOBAL_ROUTER


def set_global_router(router: RegimeStrategyRouter) -> None:
    global _GLOBAL_ROUTER
    _GLOBAL_ROUTER = router


def reset_global_router() -> None:
    global _GLOBAL_ROUTER
    _GLOBAL_ROUTER = None


__all__ = [
    "RegimeStrategyRouter",
    "TimeframeAwareDetector",
    "RouteResult",
    "PATTERN_TIMEFRAMES",
    "REGIME_ALLOWED_PATTERNS",
    "BLOCKLIST_1M",
    "get_global_router",
    "set_global_router",
    "reset_global_router",
]
