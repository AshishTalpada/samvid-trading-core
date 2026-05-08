class SelfRefGameTheory:
    """Model how your trades change market reaction."""
    def model_impact(self, trade_size: float) -> float:
        return trade_size * 0.0001
