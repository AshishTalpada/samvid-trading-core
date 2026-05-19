import logging
import math
import random
import secrets
from typing import List, Tuple

logger = logging.getLogger(__name__)


class ExecutionRandomizer:
    """
    Execution stealth randomizer. Applies Poisson-distributed inter-order delays
    and randomizes TWAP/VWAP slice sizes within +/-15% to prevent HFT pattern detection.
    """

    def randomize_slices(
        self, total_shares: int, n_slices: int, jitter_pct: float = 0.15
    ) -> List[int]:
        base = total_shares // n_slices
        slices = []
        allocated = 0
        for i in range(n_slices - 1):
            jitter = random.uniform(-jitter_pct, jitter_pct)
            s = max(1, round(base * (1 + jitter)))
            slices.append(s)
            allocated += s
        slices.append(max(1, total_shares - allocated))
        random.shuffle(slices)
        return slices

    def poisson_delays(self, n: int, mean_ms: float = 200.0) -> List[float]:
        delays = []
        for _ in range(n):
            L, k, p = math.exp(-mean_ms), 0, 1.0
            while p > L:
                k += 1
                p *= random.random()
            delays.append(float(k) / 1000.0)
        return delays
