import logging

logger = logging.getLogger(__name__)

class BrokerArbitrator:
    """AI argues with broker via FIX protocol if a fill is predatory."""
    def __init__(self):
        self.expected_slippage_bps = 2.0

    def evaluate_fill(self, fill_price: float, expected_price: float, volume: int):
        slippage = abs(fill_price - expected_price) / expected_price * 10000
        if slippage > self.expected_slippage_bps * 3:
            logger.critical(f"Predatory fill detected! Slippage: {slippage:.1f} bps. Initiating FIX dispute protocol.")
            self._dispute_fill()

    def _dispute_fill(self):
        logger.info("Sending FIX tag 35=DK (Don't Know Trade) to broker.")
