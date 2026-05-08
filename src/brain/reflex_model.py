class ReflexModel:
    """Models how YOUR trades affect subsequent market behavior (self-referential impact)."""
    def __init__(self, sensitivity: float = 0.01):
        self.sensitivity = sensitivity

    def estimate_market_reaction(self, order_size_pct_adv: float,
                                 current_trend: str) -> dict[str, float]:
        momentum_amplification = order_size_pct_adv * self.sensitivity
        if current_trend == "BULL":
            return {"price_impact": momentum_amplification, "follow_through_prob": 0.6}
        elif current_trend == "BEAR":
            return {"price_impact": -momentum_amplification, "follow_through_prob": 0.55}
        return {"price_impact": 0.0, "follow_through_prob": 0.5}
