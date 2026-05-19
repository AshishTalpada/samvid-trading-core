import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


class FactoryActivityDetector:
    """
    Detects factory operational status via infrared (thermal) satellite imagery proxies.
    High thermal signature = active production. Cold factory = shutdown or slowdown.
    Used as leading indicator for inventory/earnings surprise.
    """

    def analyse_thermal_signature(
        self, thermal_grid: np.ndarray, baseline_grid: np.ndarray
    ) -> Dict:
        if thermal_grid.shape != baseline_grid.shape:
            raise ValueError("Thermal and baseline grids must match shape.")
        delta = thermal_grid - baseline_grid
        mean_delta = float(np.mean(delta))
        hot_pixels = int(np.sum(delta > 10.0))
        cold_pixels = int(np.sum(delta < -10.0))
        status = "ACTIVE" if mean_delta > 3.0 else "SHUTDOWN" if mean_delta < -5.0 else "NORMAL"
        logger.info(
            f"[FACTORY] Mean delta: {mean_delta:.2f}°C | Hot: {hot_pixels} | Cold: {cold_pixels} | Status: {status}"
        )
        return {
            "status": status,
            "mean_delta_celsius": round(mean_delta, 2),
            "hot_pixels": hot_pixels,
        }

    def production_score(self, thermal_grid: np.ndarray, baseline_grid: np.ndarray) -> float:
        delta = float(np.mean(thermal_grid - baseline_grid))
        return min(1.0, max(0.0, (delta + 10.0) / 20.0))
