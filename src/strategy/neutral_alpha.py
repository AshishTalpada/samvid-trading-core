import logging

import numpy as np

logger = logging.getLogger(__name__)

class DeltaNeutralAlphaEngine:
    """
    Delta-neutral strategy engine. Profits from alpha signals WITHOUT directional market risk
    by simultaneously buying the signal asset and shorting a correlated hedge asset.
    Net delta ≈ 0; pure signal P&L.
    """
    def compute_hedge_ratio(self, returns_signal: list[float], returns_hedge: list[float]) -> float:
        """OLS hedge ratio: beta = Cov(signal, hedge) / Var(hedge)"""
        s = np.array(returns_signal)
        h = np.array(returns_hedge)
        n = min(len(s), len(h))
        if n < 10: return 1.0
        s, h = s[-n:], h[-n:]
        cov_matrix = np.cov(s, h)
        return float(cov_matrix[0, 1] / (cov_matrix[1, 1] + 1e-12))

    def construct_spread(self, signal_price: float, hedge_price: float, beta: float) -> float:
        """Returns the spread value (signal - beta * hedge). Mean-reverts if cointegrated."""
        return signal_price - beta * hedge_price

    def generate_signal(self, spread_series: list[float]) -> str:
        if len(spread_series) < 20: return "HOLD"
        arr = np.array(spread_series)
        mean, std = float(np.mean(arr)), float(np.std(arr))
        z = (arr[-1] - mean) / (std + 1e-9)
        if z < -2.0: return "BUY_SPREAD"    # Spread too low, expect reversion up
        if z > 2.0: return "SELL_SPREAD"    # Spread too high, expect reversion down
        return "HOLD"
