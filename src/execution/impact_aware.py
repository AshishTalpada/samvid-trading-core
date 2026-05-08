import numpy as np


class ImpactAwareExecution:
    """Prevents a trade from moving the market against itself using the square-root impact model."""
    def __init__(self, daily_volume: float, volatility: float):
        self.daily_volume = daily_volume
        self.volatility = volatility

    def max_safe_order_size(self, max_impact_bps: float = 5.0) -> float:
        """Returns the maximum order size that keeps market impact below max_impact_bps."""
        impact_threshold = max_impact_bps / 10000.0
        # Inverse of: impact = vol * sqrt(size / adv)
        if self.volatility <= 0 or self.daily_volume <= 0:
            return 0.0
        max_ratio = (impact_threshold / self.volatility) ** 2
        return float(max_ratio * self.daily_volume)
