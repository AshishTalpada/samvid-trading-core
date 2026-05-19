import logging

logger = logging.getLogger(__name__)


class VolatilitySkewAnalyzer:
    """
    Trades the difference between historical stock volatility and implied option volatility.
    """

    def __init__(self, min_skew_threshold: float = 0.15):
        self.min_skew_threshold = min_skew_threshold

    def calculate_skew_edge(
        self, historical_vol: float, implied_vol: float
    ) -> dict[str, str | float]:
        """
        Compares realized/historical volatility with market-priced implied volatility.

        Args:
            historical_vol: 20-day realized volatility (annualized).
            implied_vol: 30-day implied volatility (e.g., from VIX or specific option chain).

        Returns:
            Dictionary containing edge analysis and action.
        """
        if implied_vol <= 0 or historical_vol <= 0:
            return {"action": "HOLD", "skew_edge": 0.0}

        vol_premium = implied_vol - historical_vol
        relative_skew = vol_premium / historical_vol

        action = "HOLD"

        if relative_skew > self.min_skew_threshold:
            # Options are extremely expensive compared to actual stock movement
            action = "SELL_VOLATILITY"  # e.g., Sell Straddles / Iron Condors
            logger.info(f"Vol Skew Edge: Options heavily overpriced. Premium: {vol_premium:.2f}")
        elif relative_skew < -self.min_skew_threshold:
            # Options are extremely cheap compared to actual stock movement
            action = "BUY_VOLATILITY"  # e.g., Buy Straddles
            logger.info(
                f"Vol Skew Edge: Options heavily underpriced. Discount: {abs(vol_premium):.2f}"
            )

        return {
            "action": action,
            "historical_vol": historical_vol,
            "implied_vol": implied_vol,
            "skew_edge": relative_skew,
        }
