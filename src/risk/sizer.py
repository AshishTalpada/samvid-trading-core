import logging

logger = logging.getLogger(__name__)


class DynamicKellySizer:
    """
    Computes position sizing based on dynamic Kelly Criterion adjusted by
    Shannon Entropy of the market regime.
    High entropy = high uncertainty = lower Kelly fraction.
    """

    def __init__(self, max_capital_pct: float = 0.20):
        self.max_cap = max_capital_pct

    def compute_size(
        self, win_prob: float, win_loss_ratio: float, market_entropy: float = 1.0
    ) -> float:
        if win_prob <= 0 or win_loss_ratio <= 0:
            return 0.0

        # Standard Kelly formula: f* = p - (1-p)/b
        # where p is win_prob, b is win_loss_ratio
        kelly_f = win_prob - ((1.0 - win_prob) / win_loss_ratio)

        if kelly_f <= 0:
            return 0.0

        # Adjust Kelly fraction based on market entropy (uncertainty penalty)
        # Assuming entropy ranges from 0 (certain) to 1 (pure noise)
        entropy_penalty = max(0.1, 1.0 - market_entropy)

        # We use Half-Kelly as base for safety, then apply entropy penalty
        adjusted_f = (kelly_f * 0.5) * entropy_penalty

        final_size = min(adjusted_f, self.max_cap)
        logger.debug(
            f"[SIZER] Kelly={kelly_f:.3f}, Adj={adjusted_f:.3f}, Final Cap Pct={final_size:.2%}"
        )
        return final_size
