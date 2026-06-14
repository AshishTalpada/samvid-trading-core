import logging
import math

logger = logging.getLogger(__name__)


class DynamicHedger:
    """
    Auto-buys protective Puts / short ETF positions as underlying moves against position.
    Uses delta-hedging math: adjusts hedge ratio continuously as price changes.
    """

    def __init__(self, hedge_ratio: float = 0.5):
        self.hr = hedge_ratio

    def _black_scholes_delta(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        from scipy.stats import norm

        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0.0
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        return float(norm.cdf(d1))

    def compute_hedge_contracts(
        self, position_delta: float, option_delta: float, contract_multiplier: int = 100
    ) -> int:
        if abs(option_delta) < 1e-6:
            return 0
        contracts = -int(position_delta * self.hr / (option_delta * contract_multiplier))
        logger.info(f"[HEDGER] Position delta={position_delta:.2f} | Hedge contracts={contracts}")
        return contracts

    def hedge_signal(self, pnl_pct: float, threshold: float = -0.015) -> str:
        if pnl_pct < threshold:
            logger.warning(
                f"[HEDGER] PnL={pnl_pct:.2%} below threshold. Recommend protective hedge."
            )
            return "HEDGE_NOW"
        return "HOLD"
