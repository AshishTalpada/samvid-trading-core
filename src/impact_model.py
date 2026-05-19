import logging
import math

logger = logging.getLogger(__name__)


class MarketImpactModel:
    """
    Self-referential market impact model (Kyle's Lambda).
    Models how Sovereign's own orders permanently move price against it.
    Essential at scale: a $10M order in a $50M ADV stock = 20% participation = massive impact.
    """

    def __init__(self, kyle_lambda: float = 0.1):
        self.lam = kyle_lambda  # Price impact per unit order flow

    def price_impact_bps(self, order_size_usd: float, adv_usd: float) -> float:
        if adv_usd <= 0:
            return 0.0
        participation = order_size_usd / adv_usd
        impact_pct = self.lam * math.sqrt(participation)
        return impact_pct * 10_000

    def adjusted_entry_price(
        self, mid: float, order_size_usd: float, adv_usd: float, side: str
    ) -> float:
        impact_bps = self.price_impact_bps(order_size_usd, adv_usd)
        adj = mid * (impact_bps / 10_000)
        return mid + adj if side == "BUY" else mid - adj

    def max_safe_order_size(self, adv_usd: float, max_impact_bps: float = 5.0) -> float:
        pct = (max_impact_bps / 10_000 / self.lam) ** 2
        return adv_usd * pct
