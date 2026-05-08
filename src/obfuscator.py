import math
import random
import secrets
from typing import Tuple


class OrderObfuscator:
    """
    Institutional Execution Privacy Engine.

    Hides Sovereign's true order intent from market-makers, HFT predators,
    and dark-pool surveillance systems using three layers of obfuscation:

    1. Laplacian Size Noise — differentially private quantity masking
    2. Poisson-Distributed Time Jitter — non-uniform delay to defeat VWAP fingerprinting
    3. Iceberg Slicing — breaks large orders into random-sized child orders
       that mimic natural retail flow patterns
    """

    def __init__(
        self,
        max_time_jitter_ms: int = 50,
        max_size_jitter_pct: float = 0.15,
        laplace_sensitivity: float = 1.0,
        epsilon: float = 2.0,
    ) -> None:
        self.max_time_jitter_ms = max_time_jitter_ms
        self.max_size_jitter_pct = max_size_jitter_pct
        # Differential Privacy parameters for Laplace noise
        self.sensitivity = laplace_sensitivity
        self.epsilon = epsilon  # Privacy budget (lower = more private)

    def _laplace_noise(self) -> float:
        """Draws a sample from the Laplace distribution for differential privacy."""
        scale = self.sensitivity / self.epsilon
        u = secrets.randbelow(10**9) / 10**9 - 0.5
        return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))

    def _poisson_delay_ms(self, mean_ms: float) -> float:
        """
        Generates a Poisson-distributed delay.
        Poisson timing is much harder to fingerprint than uniform random delays
        because it statistically matches natural human-click latency distributions.
        """
        # Inverse CDF method for Poisson approximation
        L = math.exp(-mean_ms)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= random.random()
        return float(k)

    def obfuscate_order(self, target_size: int) -> Tuple[int, float]:
        """
        Applies Laplacian size noise and Poisson time jitter to a single order.

        Returns:
            (obfuscated_size, delay_seconds)
        """
        if target_size <= 1:
            return target_size, 0.0

        # Laplacian size noise (differentially private)
        dp_noise = self._laplace_noise() * target_size * self.max_size_jitter_pct
        obfuscated_size = max(1, round(target_size + dp_noise))

        # Poisson time jitter
        mean_delay_ms = self.max_time_jitter_ms / 2.0
        delay_ms = self._poisson_delay_ms(mean_delay_ms)
        delay_seconds = delay_ms / 1000.0

        return obfuscated_size, delay_seconds

    def slice_iceberg(self, total_size: int, min_slice: int = 10, max_slice: int = 200) -> list[Tuple[int, float]]:
        """
        Splits a large order into iceberg child orders with randomized sizes and delays.
        Each child order gets independently Poisson-jittered timing to prevent detection.

        Returns:
            List of (slice_size, delay_before_submission_seconds)
        """
        slices: list[Tuple[int, float]] = []
        remaining = total_size

        while remaining > 0:
            # Random child order size within bounds
            slice_size = min(remaining, random.randint(min_slice, max_slice))
            slice_size, delay = self.obfuscate_order(slice_size)
            slices.append((slice_size, delay))
            remaining -= slice_size

        return slices

    def generate_noise_orders(self, real_ticker: str, real_size: int, decoy_count: int = 3) -> list[dict]:
        """
        Generates decoy orders on correlated assets to mask the real trade.
        Decoy orders are intentionally small and immediately cancelled (spoofing-safe via IOC).
        """
        correlated_tickers = {
            "SPY": ["QQQ", "IWM", "DIA"],
            "BTC": ["ETH", "SOL", "BNB"],
            "GLD": ["SLV", "GDX", "GDXJ"],
        }.get(real_ticker, ["SPY", "QQQ"])

        decoys = []
        for i in range(min(decoy_count, len(correlated_tickers))):
            decoy_size = max(1, random.randint(1, real_size // 10))
            _, delay = self.obfuscate_order(decoy_size)
            decoys.append({
                "ticker": correlated_tickers[i],
                "size": decoy_size,
                "order_type": "IOC",
                "is_decoy": True,
                "delay_seconds": delay,
            })

        return decoys
