import logging

import numpy as np

logger = logging.getLogger(__name__)

class EvolvingLossFunctions:
    """
    Adaptive loss function selector. Switches between Sharpe, Sortino, Calmar,
    and Omega ratio maximisation based on market regime.
    """
    def sharpe(self, returns: list[float], rf: float = 0.0) -> float:
        arr = np.array(returns)
        excess = arr - rf / 252
        std = np.std(excess)
        return float(np.mean(excess) / std * np.sqrt(252)) if std > 0 else 0.0

    def sortino(self, returns: list[float], rf: float = 0.0, mar: float = 0.0) -> float:
        arr = np.array(returns)
        excess = arr - rf / 252
        downside = arr[arr < mar]
        dsd = np.std(downside) if len(downside) > 1 else 1e-9
        return float(np.mean(excess) / dsd * np.sqrt(252))

    def calmar(self, returns: list[float]) -> float:
        arr = np.array(returns)
        ann_return = float(np.mean(arr) * 252)
        cumulative = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cumulative)
        max_dd = float(np.min((cumulative - running_max) / running_max))
        return ann_return / abs(max_dd) if max_dd != 0 else 0.0

    def select_for_regime(self, regime: str) -> str:
        mapping = {"BULL": "sharpe", "BEAR": "sortino", "VOLATILE": "calmar", "CHOPPY": "sortino"}
        chosen = mapping.get(regime, "sharpe")
        logger.info(f"[LOSS FN] Regime={regime} -> using {chosen}")
        return chosen
