import logging
import random
from typing import List

logger = logging.getLogger(__name__)


class ExecutionRandomizer:
    """
    Execution stealth randomizer. Applies Poisson-distributed inter-order delays
    and randomizes TWAP/VWAP slice sizes within +/-15% to prevent HFT pattern detection.
    """

    def randomize_slices(
        self, total_shares: int, n_slices: int, jitter_pct: float = 0.15
    ) -> List[int]:
        total_shares = int(total_shares)
        n_slices = int(n_slices)
        if total_shares <= 0:
            raise ValueError("total_shares must be positive")
        if n_slices <= 0:
            raise ValueError("n_slices must be positive")

        active_slices = min(n_slices, total_shares)
        jitter_pct = max(0.0, float(jitter_pct))
        base = max(1, total_shares // active_slices)
        slices = []
        allocated = 0
        for i in range(active_slices - 1):
            jitter = random.uniform(-jitter_pct, jitter_pct)
            s = max(1, round(base * (1 + jitter)))
            remaining_after_this = active_slices - i - 1
            s = min(s, total_shares - allocated - remaining_after_this)
            slices.append(s)
            allocated += s
        slices.append(max(1, total_shares - allocated))
        random.shuffle(slices)
        return slices

    def poisson_delays(self, n: int, mean_ms: float = 200.0) -> List[float]:
        n = int(n)
        if n <= 0:
            return []
        mean_ms = max(0.0, float(mean_ms))
        if mean_ms == 0:
            return [0.0 for _ in range(n)]
        delays = []
        for _ in range(n):
            delays.append(random.expovariate(1000.0 / mean_ms))
        return delays
