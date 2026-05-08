import logging
import math
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class GameTheoryPositionSizer:
    """
    Models the market as a strategic game between Sovereign and adversarial players.
    Uses Nash Equilibrium and minimax regret to size positions considering
    how market-makers and other HFTs will react to our order flow.
    """

    def minimax_regret_size(self, expected_alpha_bps: float, impact_bps_per_unit: float, max_units: int) -> int:
        best_size, min_max_regret = 1, float("inf")
        for size in range(1, max_units + 1):
            impact = size * impact_bps_per_unit
            net_alpha = expected_alpha_bps - impact
            regret = max(0, expected_alpha_bps - net_alpha)
            max_r = max(regret, impact)
            if max_r < min_max_regret:
                min_max_regret = max_r
                best_size = size
        return best_size

    def nash_equilibrium_bid(self, value: float, n_competitors: int) -> float:
        if n_competitors <= 1:
            return value * 0.99
        factor = (n_competitors - 1) / n_competitors
        return value * factor

    def compute_optimal_size(self, alpha_bps: float, adv_usd: float, account_usd: float) -> float:
        kelly = alpha_bps / 10_000
        max_pct = 0.15
        sizing = min(kelly, max_pct) * account_usd
        logger.info(f"[GAME THEORY] Optimal size: ${sizing:,.0f} (alpha={alpha_bps:.1f}bps, kelly={kelly:.3f})")
        return sizing
