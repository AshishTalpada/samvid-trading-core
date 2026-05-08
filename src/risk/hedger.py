import logging

logger = logging.getLogger(__name__)

class MultiHorizonHedger:
    """Simultaneously hedges short-term dips and long-term crash exposure."""
    def __init__(self, short_hedge_threshold: float = -0.01, long_hedge_threshold: float = -0.05):
        self.short_threshold = short_hedge_threshold
        self.long_threshold = long_hedge_threshold

    def evaluate(self, short_term_return: float, long_term_return: float) -> dict[str, bool]:
        short_hedge = short_term_return < self.short_threshold
        long_hedge = long_term_return < self.long_threshold
        if short_hedge:
            logger.info("Short-term hedge triggered.")
        if long_hedge:
            logger.warning("Long-term crash hedge triggered.")
        return {"short_term_hedge": short_hedge, "long_term_hedge": long_hedge}
