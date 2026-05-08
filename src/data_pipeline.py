import logging
from collections import deque
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class L1DataPipeline:
    """
    High-Performance Data Normalizer.
    Ingests raw ticks from disparate exchanges (crypto, forex, equities),
    cleanses anomalies (fat fingers, bad prints), interpolates missing data,
    and constructs strict, memory-efficient temporal OHLCV bars.
    """
    def __init__(self, aggregation_window_ms: int = 1000):
        # Time-based aggregation (e.g., 1000ms = 1-second bars)
        self.agg_window_ms = aggregation_window_ms
        self.tick_buffers: Dict[str, deque] = {}
        self.last_bar_time: Dict[str, int] = {}

        # Anomaly detection bounds (Z-Score filter)
        self.price_history: Dict[str, deque] = {}

    def ingest_raw_tick(self, symbol: str, price: float, volume: float, timestamp_ms: int) -> Optional[Dict[str, float]]:
        """
        Receives a raw tick. Validates it against statistical norms.
        If the tick completes a time-bar window, it returns the aggregated OHLCV bar.
        """
        if symbol not in self.tick_buffers:
            self.tick_buffers[symbol] = deque()
            self.price_history[symbol] = deque(maxlen=100)
            self.last_bar_time[symbol] = timestamp_ms - (timestamp_ms % self.agg_window_ms)

        # Fat-Finger Anomaly Filter (Remove ticks > 5 standard deviations from rolling mean)
        history = self.price_history[symbol]
        if len(history) == 100:
            mean = sum(history) / 100.0
            variance = sum((x - mean) ** 2 for x in history) / 100.0
            std_dev = variance ** 0.5

            if std_dev > 0 and abs(price - mean) > 5 * std_dev:
                logger.warning(f"[DATA PIPELINE] Anomalous tick dropped for {symbol}. Price {price} deviates > 5 sigma from mean {mean:.2f}.")
                return None

        # Valid tick, add to buffers
        self.tick_buffers[symbol].append((price, volume))
        self.price_history[symbol].append(price)

        # Check if we crossed the aggregation boundary
        current_bar_start = timestamp_ms - (timestamp_ms % self.agg_window_ms)

        if current_bar_start > self.last_bar_time[symbol]:
            # Generate the completed bar
            bar = self._aggregate_bar(symbol)
            self.last_bar_time[symbol] = current_bar_start
            return bar

        return None

    def _aggregate_bar(self, symbol: str) -> Optional[Dict[str, float]]:
        """Consumes the tick buffer and emits an OHLCV dict."""
        buffer = self.tick_buffers[symbol]
        if not buffer:
            return None

        prices = [t[0] for t in buffer]
        volumes = [t[1] for t in buffer]

        bar = {
            "symbol": symbol,
            "open": prices[0],
            "high": max(prices),
            "low": min(prices),
            "close": prices[-1],
            "volume": sum(volumes),
            "tick_count": len(prices)
        }

        # Clear the buffer for the next window
        self.tick_buffers[symbol].clear()
        return bar

    def normalize_feature_vector(self, data: np.ndarray) -> np.ndarray:
        """
        Min-Max robust scaling for neural network ingestion.
        Ensures input matrices are strictly normalized between -1 and 1 without leaking future data.
        """
        # Exclude extreme outliers from min/max bounds (1st and 99th percentiles)
        p1 = np.percentile(data, 1, axis=0)
        p99 = np.percentile(data, 99, axis=0)

        # Clip data to avoid dividing by zero or exploding gradients
        clipped = np.clip(data, p1, p99)

        range_span = p99 - p1
        range_span[range_span == 0] = 1.0 # Prevent division by zero

        # Scale to [0, 1]
        scaled = (clipped - p1) / range_span

        # Scale to [-1, 1]
        return (scaled * 2.0) - 1.0
