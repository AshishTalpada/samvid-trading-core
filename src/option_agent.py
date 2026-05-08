import logging
import math

from scipy.stats import norm

logger = logging.getLogger(__name__)

class OptionAgent:
    """
    Analyzes Option Chains to compute Greeks and predict Gamma Squeezes based on Market Maker hedging logic.
    """
    def __init__(self, risk_free_rate: float = 0.04):
        self.r = risk_free_rate

    def _d1(self, S: float, K: float, T: float, sigma: float) -> float:
        return (math.log(S / K) + (self.r + sigma**2 / 2.0) * T) / (sigma * math.sqrt(T))

    def calculate_gamma(self, S: float, K: float, T: float, sigma: float) -> float:
        """Black-Scholes Gamma: The rate of change of Delta."""
        if T <= 0 or sigma <= 0: return 0.0
        d1 = self._d1(S, K, T, sigma)
        pdf_d1 = norm.pdf(d1)
        return pdf_d1 / (S * sigma * math.sqrt(T))

    def predict_squeeze(self, spot_price: float, option_chain: list[dict]) -> dict:
        """
        Aggregates Total Dealer Gamma. If Market Makers are short massive amounts of Gamma,
        a sharp upward move forces them to buy the underlying, triggering a Gamma Squeeze.
        """
        total_dealer_gamma = 0.0

        for opt in option_chain:
            # opt expected to have: strike, dte (days to exp), iv (implied vol), open_interest, type (call/put), dealer_position (long/short)
            T = opt['dte'] / 365.0
            gamma_per_contract = self.calculate_gamma(spot_price, opt['strike'], T, opt['iv'])

            position_multiplier = 1.0 if opt['dealer_position'] == 'long' else -1.0
            total_dealer_gamma += gamma_per_contract * opt['open_interest'] * 100 * position_multiplier

        # If dealers are short gamma, they must buy into rallies (positive feedback loop)
        squeeze_risk = total_dealer_gamma < -1000000.0 # Arbitrary threshold for major short gamma

        return {
            "total_dealer_gamma": total_dealer_gamma,
            "squeeze_imminent": squeeze_risk,
            "hedging_flow_estimate": -total_dealer_gamma * 0.01 # Rough estimate of shares needed to delta hedge a 1% move
        }
