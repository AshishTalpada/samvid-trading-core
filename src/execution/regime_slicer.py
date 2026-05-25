import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class RegimeAwareSlicer:
    """
    Adapts order slicing strategy based on market regime.
    BULL: aggressive TWAP with fewer slices (trending — urgency beats cost).
    CHOPPY: smaller, slower slices to avoid false breakouts.
    VOLATILE: immediate 1-shot market order if VIX > 30 (cannot wait for fills).
    """

    REGIME_PARAMS = {
        "BULL": {"n_slices": 5, "interval_min": 2.0, "urgency": "MEDIUM"},
        "BEAR": {"n_slices": 10, "interval_min": 5.0, "urgency": "LOW"},
        "CHOPPY": {"n_slices": 15, "interval_min": 3.0, "urgency": "LOW"},
        "VOLATILE": {"n_slices": 1, "interval_min": 0.0, "urgency": "IMMEDIATE"},
    }

    def compute_schedule(self, total_shares: int, regime: str) -> List[Tuple[int, float]]:
        total_shares = int(total_shares)
        if total_shares <= 0:
            raise ValueError("total_shares must be positive")

        params = self.REGIME_PARAMS.get(regime, self.REGIME_PARAMS["CHOPPY"])
        n = min(int(params["n_slices"]), total_shares)
        interval = float(params["interval_min"]) * 60
        base = max(1, total_shares // n)
        allocated = 0
        schedule = []
        for i in range(n):
            if i == n - 1:
                size = total_shares - allocated
            else:
                remaining_after_this = n - i - 1
                size = min(base, total_shares - allocated - remaining_after_this)
            schedule.append((max(1, size), i * interval))
            allocated += max(1, size)
        logger.info(
            f"[REGIME SLICER] {regime}: {n} slices over {n * params['interval_min']:.0f} mins"
        )  # type: ignore
        return schedule
