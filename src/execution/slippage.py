import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class SlippageModel:
    """Predicts expected slippage (price tax) based on L2 order book depth."""

    def __init__(self, base_impact_bps: float = 1.5):
        self.base_impact_bps = base_impact_bps

    def predict_slippage(self, order_size: float, bid_ask_spread: float,
                         book_liquidity_at_price: float) -> float:
        """
        Estimates the slippage for a given order size against current liquidity.
        
        Args:
            order_size: Dollar amount of the order.
            bid_ask_spread: Current spread percentage (e.g., 0.0005 for 5 bps).
            book_liquidity_at_price: Dollar amount of resting limit orders at top of book.
            
        Returns:
            Expected slippage in percentage terms (e.g., 0.0010 for 10 bps).
        """
        if book_liquidity_at_price <= 0:
            logger.warning("Zero liquidity detected at top of book. Slippage risk high.")
            return bid_ask_spread * 3.0

        # Square root impact model: Impact ~ sqrt(OrderSize / Liquidity)
        ratio = order_size / book_liquidity_at_price
        impact = self.base_impact_bps * (ratio ** 0.5) / 10000.0

        expected_slippage = (bid_ask_spread / 2.0) + impact
        return float(expected_slippage)
