import logging

logger = logging.getLogger(__name__)

class DynamicHedger:
    """Auto-scales put option hedges as underlying price moves against position."""
    def __init__(self, delta_per_pct_move: float = 0.05):
        self.delta_per_pct_move = delta_per_pct_move

    def calculate_hedge_delta(self, entry_price: float, current_price: float) -> float:
        pct_move = (current_price - entry_price) / entry_price
        hedge_delta = abs(pct_move) * self.delta_per_pct_move
        if pct_move < -0.02:
            logger.info(f"Dynamic hedge triggered. pct_move={pct_move:.2%} delta={hedge_delta:.3f}")
        return min(1.0, hedge_delta)
