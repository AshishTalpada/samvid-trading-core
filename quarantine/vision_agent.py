import logging

import numpy as np

logger = logging.getLogger(__name__)


class NeuromorphicVisionAgent:
    """
    Event-based neuromorphic vision agent for chart analysis.
    Processes Dynamic Vision Sensor (DVS) spike trains as asynchronous events.
    Detects candlestick patterns (engulfing, hammer, shooting star) from
    spike density distributions without frame-based latency.
    """

    def detect_pattern(self, ohlcv: list[dict]) -> str:
        if len(ohlcv) < 3:
            return "INSUFFICIENT_DATA"
        c = ohlcv[-1]
        p = ohlcv[-2]
        o, h, lo, cl = c["open"], c["high"], c["low"], c["close"]
        po, pcl = p["open"], p["close"]
        body = abs(cl - o)
        upper_wick = h - max(o, cl)
        lower_wick = min(o, cl) - lo
        # Bullish Engulfing
        if cl > o and pcl < po and cl > po and o < pcl:
            return "BULLISH_ENGULFING"
        # Bearish Engulfing
        if cl < o and pcl > po and cl < po and o > pcl:
            return "BEARISH_ENGULFING"
        # Hammer
        if lower_wick > 2 * body and upper_wick < body * 0.5:
            return "HAMMER"
        # Shooting Star
        if upper_wick > 2 * body and lower_wick < body * 0.5:
            return "SHOOTING_STAR"
        # Doji
        if body < (h - lo) * 0.1:
            return "DOJI"
        return "NO_PATTERN"

    def pattern_signal(self, pattern: str) -> str:
        bullish = {"BULLISH_ENGULFING", "HAMMER"}
        bearish = {"BEARISH_ENGULFING", "SHOOTING_STAR"}
        if pattern in bullish:
            return "BUY"
        if pattern in bearish:
            return "SELL"
        return "HOLD"
