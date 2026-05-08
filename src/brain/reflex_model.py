import logging

import numpy as np

logger = logging.getLogger(__name__)

class MarketReflexModel:
    """
    Self-Referential Game Theory Model.
    Predicts how the market (specifically HFT algorithms) will react to OUR trade size.
    If Sovereign buys 10,000 shares, do HFTs front-run the next 10,000?
    """
    def __init__(self, avg_daily_volume: float):
        self.adv = avg_daily_volume

    def opponent_response(self, intended_size: float, bid_ask_spread: float) -> float:
        # Predicts price impact (slippage) caused by our own order
        participation_rate = intended_size / (self.adv * 0.01 + 1)

        # Non-linear impact model based on square root law of market impact
        impact = 0.1 * bid_ask_spread * np.sqrt(participation_rate)
        return float(impact)

    def nash_optimal_size(self, intended_size: float, bid_ask_spread: float, max_tolerable_impact: float) -> float:
        impact = self.opponent_response(intended_size, bid_ask_spread)
        if impact <= max_tolerable_impact:
            return intended_size

        # Binary search for optimal size that keeps impact below threshold
        low, high = 0.0, intended_size
        optimal = 0.0
        for _ in range(10):
            mid = (low + high) / 2
            if self.opponent_response(mid, bid_ask_spread) <= max_tolerable_impact:
                optimal = mid
                low = mid
            else:
                high = mid

        logger.info(f"[REFLEX] Capped size at {optimal:.0f} to prevent triggering HFT front-running.")
        return optimal
