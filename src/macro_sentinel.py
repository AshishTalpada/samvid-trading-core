import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class ContagionSentinel:
    """
    Detects when a crash in one asset class starts spreading (contagion) to others.
    Key signal: correlations SPIKE above 0.9 during market stress (Correlation Breakdown).
    When everything crashes together, diversification fails.
    """
    def __init__(self, lookback: int = 20, contagion_threshold: float = 0.85):
        self.lookback = lookback
        self.threshold = contagion_threshold

    def detect_contagion(self, asset_returns: Dict[str, List[float]]) -> Dict:
        tickers = list(asset_returns.keys())
        if len(tickers) < 2: return {"contagion": False, "avg_correlation": 0.0}
        matrix = np.array([asset_returns[t][-self.lookback:] for t in tickers])
        if matrix.shape[1] < 5: return {"contagion": False, "avg_correlation": 0.0}
        corr = np.corrcoef(matrix)
        upper = corr[np.triu_indices(len(tickers), k=1)]
        avg_corr = float(np.mean(upper))
        contagion = avg_corr > self.threshold
        if contagion: logger.warning(f"[SENTINEL] CONTAGION DETECTED! avg_corr={avg_corr:.2f}")
        return {"contagion": contagion, "avg_correlation": round(avg_corr, 3), "tickers": tickers}
