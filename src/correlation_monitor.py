import logging
from collections import deque
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class CorrelationBreakdownMonitor:
    """
    Real-time cross-asset correlation regime monitor.
    In normal markets, asset correlations are stable. During a crisis,
    ALL correlations spike toward 1.0 — diversification fails catastrophically.
    Detects this breakdown using a rolling correlation matrix and
    triggers immediate portfolio de-risking when detected.
    """

    def __init__(self, window: int = 20, contagion_threshold: float = 0.80):
        self.window = window
        self.threshold = contagion_threshold
        self._returns: Dict[str, deque] = {}

    def ingest(self, ticker: str, daily_return: float) -> None:
        if ticker not in self._returns:
            self._returns[ticker] = deque(maxlen=self.window)
        self._returns[ticker].append(daily_return)

    def correlation_matrix(self) -> np.ndarray | None:
        tickers = [t for t, buf in self._returns.items() if len(buf) >= self.window]
        if len(tickers) < 2:
            return None
        matrix = np.array([list(self._returns[t]) for t in tickers])
        return np.corrcoef(matrix)

    def avg_pairwise_correlation(self) -> float:
        corr = self.correlation_matrix()
        if corr is None:
            return 0.0
        n = corr.shape[0]
        upper = [corr[i, j] for i in range(n) for j in range(i + 1, n)]
        return float(np.mean(upper)) if upper else 0.0

    def is_contagion_detected(self) -> bool:
        avg = self.avg_pairwise_correlation()
        detected = avg > self.threshold
        if detected:
            logger.critical(
                f"[CORR MONITOR] CONTAGION DETECTED! avg_corr={avg:.2f} > {self.threshold}. "
                "All correlations converging — reduce ALL positions immediately."
            )
        return detected

    def risk_multiplier(self) -> float:
        avg = self.avg_pairwise_correlation()
        # Returns 1.0 at normal corr, approaches 0.0 as corr->1.0 (kill sizing)
        return max(0.1, 1.0 - avg)
