import logging
from collections import deque
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


class ContagionSentinel:
    """
    Detects cross-asset contagion - e.g. crypto sell-off bleeding into tech.
    Maintains a rolling correlation window. A sudden spike in correlation across normally
    uncorrelated assets indicates a liquidity event / systemic shock.
    """

    def __init__(self, window: int = 20, correlation_spike_threshold: float = 0.5):
        self.window = window
        self.threshold = correlation_spike_threshold
        self._history: Dict[str, deque] = {}

    def ingest(self, symbol: str, returns: float) -> None:
        if symbol not in self._history:
            self._history[symbol] = deque(maxlen=self.window)
        self._history[symbol].append(returns)

    def detect_contagion(self, baseline_correlation: float = 0.2) -> bool:
        if len(self._history) < 2:
            return False

        valid_symbols = [s for s, hist in self._history.items() if len(hist) == self.window]
        if len(valid_symbols) < 2:
            return False

        matrix = np.array([list(self._history[s]) for s in valid_symbols])
        corr_matrix = np.corrcoef(matrix)

        n = corr_matrix.shape[0]
        upper_tri = [corr_matrix[i, j] for i in range(n) for j in range(i + 1, n)]
        avg = float(np.nanmean(upper_tri)) if upper_tri else 0.0
        current_avg_corr = avg if np.isfinite(avg) else 0.0

        spike = current_avg_corr - baseline_correlation
        if spike > self.threshold:
            logger.critical(
                f"[CONTAGION] Detected systemic correlation spike: {current_avg_corr:.2f} (jumped {spike:.2f})"
            )
            return True
        return False
