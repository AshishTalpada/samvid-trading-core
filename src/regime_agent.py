import numpy as np
from typing import Literal

RegimeType = Literal["BULL", "BEAR", "CHOP"]

class RegimeAgent:
    """Bayesian regime detection using rolling returns and volatility."""
    def __init__(self, window: int = 20):
        self.window = window

    def detect_regime(self, prices: list[float]) -> RegimeType:
        if len(prices) < self.window + 1:
            return "CHOP"
        arr = np.array(prices[-(self.window + 1):])
        returns = np.diff(arr) / arr[:-1]
        mu = np.mean(returns)
        vol = np.std(returns)
        if mu > vol * 0.5:
            return "BULL"
        elif mu < -vol * 0.5:
            return "BEAR"
        return "CHOP"
