"""
Chaos Agent (#105 from SOVEREIGN_ULTIMATE_CHECKLIST).
Calculates Lyapunov exponents for market 'Randomness' to detect chaos levels.
"""

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ChaosAgent:
    """
    Chaos Metrics Agent - measures market predictability via Lyapunov exponents.
    
    High positive Lyapunov = chaotic/unpredictable (avoid new positions)
    Low/Negative Lyapunov = stable/predictable (favorable for entries)
    """

    def __init__(self):
        self.history = []

    def calculate_lyapunov(
        self,
        prices: list[float],
        embedding_dim: int = 5,
        tau: int = 1,
    ) -> Optional[float]:
        """
        Calculate the maximum Lyapunov exponent using Rosenstein algorithm.
        
        Args:
            prices: List of price values
            embedding_dim: Dimension for time-delay embedding
            tau: Time delay for embedding
            
        Returns:
            Maximum Lyapunov exponent or None if insufficient data
        """
        if len(prices) < embedding_dim * 3:
            logger.warning(f"Insufficient data for Lyapunov calculation: {len(prices)} points")
            return None

        try:
            data = np.array(prices)

            time_series = self._create_embedding(data, embedding_dim, tau)
            if time_series.shape[0] < 10:
                return None

            lyap = self._rosenstein_algorithm(time_series)
            return lyap

        except Exception as e:
            logger.error(f"Lyapunov calculation failed: {e}")
            return None

    def _create_embedding(self, data: np.ndarray, dim: int, tau: int) -> np.ndarray:
        """Create time-delay embedding matrix."""
        n = len(data) - (dim - 1) * tau
        if n <= 0:
            return np.array([])

        embedding = np.zeros((n, dim))
        for i in range(dim):
            embedding[:, i] = data[i * tau : i * tau + n]

        return embedding

    def _rosenstein_algorithm(self, embedding: np.ndarray, max_iter: int = 50) -> float:
        """
        Simplified Rosenstein algorithm for Lyapunov estimation.
        """
        n, dim = embedding.shape

        divergence_exponents = []
        log_distances = []

        for iteration in range(1, max_iter + 1):
            mean_div = 0.0
            count = 0

            for i in range(n - iteration):
                if i >= n - iteration:
                    continue

                reference = embedding[i]
                neighbor_idx = self._find_nearest_neighbor(embedding, reference, exclude_indices=[i])

                if neighbor_idx is not None and neighbor_idx + iteration < n:
                    dist_0 = np.linalg.norm(embedding[i] - embedding[neighbor_idx])
                    dist_t = np.linalg.norm(
                        embedding[i + iteration] - embedding[neighbor_idx + iteration]
                    )

                    if dist_0 > 1e-10 and dist_t > 1e-10:
                        mean_div += np.log(dist_t / dist_0)
                        log_distances.append(np.log(dist_t))
                        count += 1

            if count > 0:
                mean_div /= count
                divergence_exponents.append(mean_div / iteration)

        if divergence_exponents:
            return np.mean(divergence_exponents[-10:])
        return 0.0

    def _find_nearest_neighbor(
        self, embedding: np.ndarray, point: np.ndarray, exclude_indices: list[int]
    ) -> Optional[int]:
        """Find the nearest neighbor to a point, excluding specified indices."""
        min_dist = float("inf")
        nearest_idx = None

        for i in range(len(embedding)):
            if i in exclude_indices:
                continue

            dist = np.linalg.norm(point - embedding[i])
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        return nearest_idx

    def calculate_correlation_dimension(
        self, prices: list[float], scale_range: tuple[int, int] = (2, 20)
    ) -> Optional[float]:
        """
        Calculate correlation dimension as another measure of chaos.
        
        Args:
            prices: Price time series
            scale_range: Range of box sizes to test
            
        Returns:
            Correlation dimension estimate
        """
        if len(prices) < 100:
            return None

        try:
            data = np.array(prices).reshape(-1, 1)

            scales = range(scale_range[0], scale_range[1] + 1)
            counts = []

            for scale in scales:
                count = 0
                for i in range(len(data)):
                    for j in range(i + 1, len(data)):
                        if np.abs(data[i] - data[j])[0] < scale:
                            count += 1
                counts.append(count)

            scales_arr = np.array(list(scales))
            counts_arr = np.array(counts)

            valid = counts_arr > 0
            if valid.sum() < 2:
                return None

            log_scales = np.log(scales_arr[valid])
            log_counts = np.log(counts_arr[valid])

            if len(log_scales) < 2:
                return None

            slope = np.polyfit(log_scales, log_counts, 1)[0]
            return slope

        except Exception as e:
            logger.debug(f"Correlation dimension calculation failed: {e}")
            return None

    def analyze_market_chaos(
        self,
        prices: list[float],
        embedding_dim: int = 5,
    ) -> dict[str, Any]:
        """
        Comprehensive chaos analysis of market prices.
        
        Returns:
            Dictionary with chaos metrics and trading recommendations
        """
        lyapunov = self.calculate_lyapunov(prices, embedding_dim)
        corr_dim = self.calculate_correlation_dimension(prices)

        chaos_level = "UNKNOWN"
        recommendation = "HOLD"

        if lyapunov is not None:
            if lyapunov > 0.5:
                chaos_level = "HIGH_CHAOS"
                recommendation = "AVOID_NEW_POSITIONS"
            elif lyapunov > 0.1:
                chaos_level = "MODERATE_CHAOS"
                recommendation = "REDUCE_SIZE"
            elif lyapunov > -0.1:
                chaos_level = "STABLE"
                recommendation = "NORMAL_OPERATION"
            else:
                chaos_level = "HIGHLY_PREDICTABLE"
                recommendation = "INCREASE_SIZE"

        return {
            "lyapunov_exponent": lyapunov,
            "correlation_dimension": corr_dim,
            "chaos_level": chaos_level,
            "recommendation": recommendation,
            "data_points": len(prices),
            "embedding_dim": embedding_dim,
        }

    def get_historical_chaos(self) -> list[dict[str, Any]]:
        """Return historical chaos measurements."""
        return self.history


_chaos_agent_instance: Optional[ChaosAgent] = None


def get_chaos_agent() -> ChaosAgent:
    """Get the singleton ChaosAgent instance."""
    global _chaos_agent_instance
    if _chaos_agent_instance is None:
        _chaos_agent_instance = ChaosAgent()
    return _chaos_agent_instance
