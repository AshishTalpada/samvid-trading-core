import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


class TailRiskModel:
    """
    Extreme Value Theory (EVT) tail risk model.
    Fits a Generalised Pareto Distribution (GPD) to exceedances beyond a threshold
    to model the 1% worst-case loss far more accurately than normal distribution VaR.
    """

    def __init__(self, threshold_pct: float = 0.05):
        self.u = threshold_pct  # Threshold: exceedances beyond this percentile

    def fit_gpd(self, losses: list[float]) -> tuple[float, float]:
        """Fits GPD via method of moments. Returns (xi, sigma)."""
        arr = np.array(losses)
        threshold = float(np.percentile(arr, (1 - self.u) * 100))
        exceedances = arr[arr > threshold] - threshold
        if len(exceedances) < 5:
            return 0.0, float(np.std(arr))
        mean_e = float(np.mean(exceedances))
        var_e = float(np.var(exceedances))
        sigma = mean_e * (1 + var_e / mean_e**2) / 2
        xi = (var_e / mean_e**2 - 1) / 2
        return xi, sigma

    def expected_shortfall(self, losses: list[float], confidence: float = 0.99) -> float:
        xi, sigma = self.fit_gpd(losses)
        u_loss = float(np.percentile(losses, (1 - self.u) * 100))
        n = len(losses)
        n_u = sum(1 for l in losses if l > u_loss)
        if n_u == 0 or (1 - xi) == 0:
            return float(np.mean(sorted(losses)[-int(n * (1 - confidence)):]))
        var_gpd = u_loss + (sigma / (1 - xi)) * ((n / n_u * (1 - confidence)) ** (-xi) - 1)
        es = (var_gpd + sigma - xi * u_loss) / (1 - xi)
        logger.info(f"[TAIL RISK] GPD ES@{confidence:.0%}: {es:.4f} (xi={xi:.3f}, sigma={sigma:.4f})")
        return float(es)
