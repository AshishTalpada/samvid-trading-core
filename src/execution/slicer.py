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
        self.num_slices = max(1, int(num_slices))
        self.time_variance_pct = max(0.0, float(time_variance_pct))
        self.epsilon = max(0.1, float(epsilon))  # Differential privacy budget

    def _laplace_noise(self, scale: float) -> float:
        u = secrets.randbelow(10**9) / 10**9 - 0.5
        u = max(-0.4999, min(0.4999, u))  # prevent log(0) at boundary
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    def _poisson_delay(self, mean_secs: float) -> float:
        if mean_secs <= 0:
            return 0.0
        return random.expovariate(1.0 / mean_secs)

    def generate_slices(self, total_size: int, total_duration_secs: float) -> List[dict]:
        total_size = int(total_size)
        if total_size <= 0:
            raise ValueError("total_size must be positive")

        active_slices = min(self.num_slices, total_size)
        total_duration_secs = max(0.0, float(total_duration_secs))
        base_size = max(1, total_size // active_slices)
        base_delay = total_duration_secs / active_slices
        slices = []
        allocated = 0

        for i in range(active_slices):
            noise = self._laplace_noise(base_size * (1.0 / self.epsilon) * self.time_variance_pct)
            remaining_after_this = active_slices - i - 1
            if i == active_slices - 1:
                size = max(1, total_size - allocated)
            else:
                size = max(1, int(base_size + noise))
                max_size_now = total_size - allocated - remaining_after_this
                size = min(size, max(1, max_size_now))

            delay = self._poisson_delay(base_delay)
            venue = self.DEFAULT_VENUES[i % len(self.DEFAULT_VENUES)]

            slices.append({"size": size, "delay_secs": round(delay, 4), "venue": venue})
            allocated += size

        logger.info(
            f"[SLICER] Generated {active_slices} slices for {total_size} shares "
            f"over {total_duration_secs:.0f}s across {len(set(s['venue'] for s in slices))} venues"
        )
        return slices

    def adaptive_slice_count(self, order_size: int, adv: int, urgency: str = "NORMAL") -> int:
        participation = order_size / max(adv, 1)
        base = max(3, int(participation * 50))
        multiplier = {"LOW": 2, "NORMAL": 1, "HIGH": 0.5, "IMMEDIATE": 0}.get(urgency, 1)
        return max(1, int(base * multiplier))
