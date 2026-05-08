import logging
import math

logger = logging.getLogger(__name__)

class MarketReflexModel:
    """
    Self-referential game theory model.
    Models how the market will REACT to Sovereign's own trades.
    Large orders telegraph intent → adversarial players front-run.
    Calculates the Nash equilibrium execution strategy.
    """
    def __init__(self, kyle_lambda: float = 0.1):
        self.lam = kyle_lambda

    def opponent_response(self, order_size_usd: float, adv_usd: float) -> dict:
        participation = order_size_usd / adv_usd if adv_usd > 0 else 0
        front_run_prob = min(0.95, participation * 2.5)
        adverse_impact_bps = self.lam * math.sqrt(participation) * 10_000
        return {"front_run_probability": round(front_run_prob, 3), "adverse_impact_bps": round(adverse_impact_bps, 2)}

    def nash_optimal_size(self, alpha_bps: float, adv_usd: float) -> float:
        optimal_participation = (alpha_bps / (10_000 * self.lam)) ** 2
        return adv_usd * optimal_participation
