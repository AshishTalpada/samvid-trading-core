import logging
import math
import random
import secrets
from typing import List

logger = logging.getLogger(__name__)


class StealthSlicer:
    """
    Institutional-grade stealth order slicer.
    Combines three anti-detection techniques:
    1. Randomized slice sizing with Laplace noise
    2. Poisson-distributed inter-order delays (matches natural HFT latency distributions)
    3. Venue rotation to prevent single-venue concentration fingerprinting
    """

    DEFAULT_VENUES = ["EDGX", "ARCA", "BATS", "NASDAQ", "IEX"]

    def __init__(
        self,
        num_slices: int = 10,
        time_variance_pct: float = 0.3,
        epsilon: float = 2.0,
    ):
        self.num_slices = num_slices
        self.time_variance_pct = time_variance_pct
        self.epsilon = epsilon  # Differential privacy budget

    def _laplace_noise(self, scale: float) -> float:
        u = secrets.randbelow(10**9) / 10**9 - 0.5
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    def _poisson_delay(self, mean_secs: float) -> float:
        L = math.exp(-mean_secs * 1000)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k / 1000.0

    def generate_slices(self, total_size: int, total_duration_secs: float) -> List[dict]:
        base_size = total_size // self.num_slices
        base_delay = total_duration_secs / self.num_slices
        slices = []
        allocated = 0

        for i in range(self.num_slices):
            noise = self._laplace_noise(base_size * (1.0 / self.epsilon) * self.time_variance_pct)
            if i == self.num_slices - 1:
                size = max(1, total_size - allocated)
            else:
                size = max(1, int(base_size + noise))
                size = min(size, total_size - allocated - (self.num_slices - i - 1))

            delay = self._poisson_delay(base_delay)
            venue = self.DEFAULT_VENUES[i % len(self.DEFAULT_VENUES)]

            slices.append({"size": size, "delay_secs": round(delay, 4), "venue": venue})
            allocated += size

        logger.info(
            f"[SLICER] Generated {self.num_slices} slices for {total_size} shares "
            f"over {total_duration_secs:.0f}s across {len(set(s['venue'] for s in slices))} venues"
        )
        return slices

    def adaptive_slice_count(self, order_size: int, adv: int, urgency: str = "NORMAL") -> int:
        participation = order_size / max(adv, 1)
        base = max(3, int(participation * 50))
        multiplier = {"LOW": 2, "NORMAL": 1, "HIGH": 0.5, "IMMEDIATE": 0}.get(urgency, 1)
        return max(1, int(base * multiplier))
