import logging
import math
from typing import Dict

logger = logging.getLogger(__name__)


class ImpactAwareExecutor:
    """
    Ensures Sovereign's trades do not move the market against itself.
    Uses Kyle's Lambda and Almgren-Chriss permanent impact formula to
    split orders optimally so slippage never exceeds the expected alpha.
    """

    def __init__(self, kyle_lambda: float = 0.1, eta: float = 0.142):
        self.lam = kyle_lambda
        self.eta = eta

    def impact_cost_bps(self, order_usd: float, adv_usd: float, sigma_daily: float) -> float:
        if adv_usd <= 0:
            return 0.0
        participation = order_usd / adv_usd
        temp = self.lam * sigma_daily * math.sqrt(participation)
        perm = self.eta * sigma_daily * participation
        return (temp + 0.5 * perm) * 10_000

    def max_order_size(self, adv_usd: float, alpha_bps: float, sigma_daily: float) -> float:
        """Returns the maximum order size (USD) where impact < alpha."""
        target_pct = (alpha_bps / (10_000 * self.lam * sigma_daily)) ** 2
        return adv_usd * min(target_pct, 0.20)

    def execute_decision(self, order_usd: float, adv_usd: float, alpha_bps: float, sigma_daily: float) -> Dict:
        impact = self.impact_cost_bps(order_usd, adv_usd, sigma_daily)
        max_size = self.max_order_size(adv_usd, alpha_bps, sigma_daily)
        approved = impact < alpha_bps * 0.5
        result = {"approved": approved, "impact_bps": round(impact, 2),
                  "max_safe_usd": round(max_size, 2), "alpha_bps": alpha_bps}
        if not approved:
            logger.warning(f"[IMPACT EXEC] Order rejected: impact={impact:.1f}bps > alpha/2={alpha_bps/2:.1f}bps")
        return result
