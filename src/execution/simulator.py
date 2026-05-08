import logging

import numpy as np

logger = logging.getLogger(__name__)

class ImpactSimulator:
    """Execution edge: Model how your trades will move the market (Slippage/Impact)."""
    def __init__(self, adv_data: dict):
        self.adv = adv_data # Average Daily Volume

    def calculate_market_impact(self, ticker: str, order_size: int, volatility: float) -> float:
        """
        Uses the Almgren-Chriss Square Root model for temporary market impact.
        Impact = Gamma * Volatility * sqrt(OrderSize / ADV)
        """
        daily_vol = self.adv.get(ticker, 1000000)
        gamma = 0.314 # Empirical coefficient

        if daily_vol <= 0: return 0.0

        participation_rate = order_size / daily_vol
        impact_bps = gamma * volatility * np.sqrt(participation_rate) * 10000

        logger.debug(f"Estimated Market Impact for {order_size} {ticker}: {impact_bps:.2f} bps")
        return impact_bps
