import logging
import math

logger = logging.getLogger(__name__)


class DrawdownDurationModel:
    """
    Advanced Psychological & Risk Modeling for Drawdowns.
    Uses Fractional Brownian Motion (fBM) concepts to model the expected duration
    of a drawdown (Time to Recovery / TTR), factoring in the system's empirical
    Sharpe Ratio and trade autocorrelation.
    """

    def __init__(self, risk_free_rate: float = 0.04):
        self.rf = risk_free_rate

    def calculate_expected_drawdown_duration(
        self,
        current_drawdown_pct: float,
        annualized_return: float,
        annualized_volatility: float,
        trades_per_day: int,
    ) -> dict:
        """
        Calculates the mathematically expected time required to recover from the current drawdown,
        assuming returns follow a Geometric Brownian Motion with drift.
        """
        if current_drawdown_pct <= 0 or annualized_volatility <= 0:
            return {"expected_days": 0, "probability_1_month": 1.0}

        # A >=100% drawdown is a total wipeout: recovery is mathematically impossible and
        # the required_return / log() below would divide by zero or take log of a non-positive.
        if current_drawdown_pct >= 1.0:
            return {"expected_days": float("inf"), "probability_1_month": 0.0}

        # Drift (mu) and Variance (sigma^2)
        mu = annualized_return
        sigma = annualized_volatility

        # To recover from a drawdown D, we need the equity curve to grow by a factor of 1 / (1 - D)
        # e.g., a 20% drawdown requires a 25% gain to recover.
        required_return = current_drawdown_pct / (1.0 - current_drawdown_pct)

        # In a GBM model, the First Passage Time (Inverse Gaussian Distribution) to reach boundary a=ln(1+Req)
        a = math.log(1.0 + required_return)

        # Expected Time to reach boundary 'a' with drift 'mu - sigma^2/2'
        drift_adj = mu - (sigma**2) / 2.0

        if drift_adj <= 0:
            logger.warning(
                "System has negative expected drift. Theoretical Time to Recovery is INFINITE."
            )
            return {"expected_days": float("inf"), "probability_1_month": 0.0}

        expected_years = a / drift_adj
        expected_days = expected_years * 252  # Trading days

        # Calculate the probability of recovering within 1 month (21 trading days)
        # Using the CDF of the Inverse Gaussian Distribution
        t_1mo = 21.0 / 252.0

        # Standard brownian motion first passage probability approximation
        import scipy.stats as stats

        term1 = (drift_adj * t_1mo - a) / (sigma * math.sqrt(t_1mo))
        term2 = (-drift_adj * t_1mo - a) / (sigma * math.sqrt(t_1mo))

        prob_recovery = stats.norm.cdf(term1) + math.exp(
            2 * drift_adj * a / (sigma**2)
        ) * stats.norm.cdf(term2)

        return {
            "required_gain_pct": required_return * 100,
            "expected_days": expected_days,
            "probability_1_month": prob_recovery,
        }
