import logging
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class AlternativeDataAggregator:
    """
    Aggregates proprietary alternative data signals into a single composite score.
    Combines: satellite imagery, shipping data, credit card spending,
    job posting velocity, and app-download trends.
    """

    def __init__(self):
        self._signals: Dict[str, float] = {}

    def ingest(self, source: str, value: float, confidence: float = 1.0) -> None:
        self._signals[source] = value * confidence
        logger.debug(f"[ALT DATA] {source}: {value:.4f} (conf={confidence:.2f})")

    def composite_score(self) -> float:
        if not self._signals:
            return 0.0
        return sum(self._signals.values()) / len(self._signals)

    def bullish_signal_count(self) -> int:
        return sum(1 for v in self._signals.values() if v > 0)

    def alt_data_summary(self) -> Dict:
        composite = self.composite_score()
        signal = "BULLISH" if composite > 0.2 else "BEARISH" if composite < -0.2 else "NEUTRAL"
        return {
            "composite": round(composite, 4),
            "signal": signal,
            "sources": len(self._signals),
            "bullish": self.bullish_signal_count(),
        }
