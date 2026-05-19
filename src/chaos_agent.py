import asyncio
import ctypes
import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np

from config import PROJECT_PATH

logger = logging.getLogger(__name__)


class ChaosAgent:
    """
    Sovereign Chaos Agent.
    1. Lyapunov Exponent (LLE) calculation for market randomness detection.
    2. Chaos Monkey functionality for shadow environment stress testing.
    """

    def __init__(self, failure_probability: float = 0.01):
        self.failure_prob = failure_probability
        self.faults_injected = 0
        self._lib = None
        self._load_shared_library()

    def _load_shared_library(self):
        """Loads the C++ chaos metrics library for ultra-fast LLE calculation."""
        try:
            # Determine extension based on OS
            ext = ".dll" if os.name == "nt" else ".so"
            lib_path = os.path.join(PROJECT_PATH, f"libsovereign{ext}")

            if os.path.exists(lib_path):
                self._lib = ctypes.CDLL(lib_path)
                self._lib.compute_lyapunov_exponent.argtypes = [
                    ctypes.POINTER(ctypes.c_double),
                    ctypes.c_int,
                    ctypes.c_int,
                    ctypes.c_int,
                ]
                self._lib.compute_lyapunov_exponent.restype = ctypes.c_double
                logger.info(f" Chaos Metrics library ({ext}) loaded successfully.")
            else:
                logger.warning(
                    f"Chaos Metrics library (libsovereign{ext}) not found. Falling back to Python metrics (slow)."
                )
        except Exception as e:
            logger.error(f"Failed to load Chaos Metrics library: {e}")

    def calculate_market_randomness(self, prices: List[float]) -> float:
        """
        Calculates the Largest Lyapunov Exponent (LLE).
        LLE > 0: Deterministic Chaos (potentially predictable).
        LLE <= 0: Random Walk or Mean Reverting.
        """
        if len(prices) < 50:
            return 0.0

        if self._lib:
            try:
                c_prices = (ctypes.c_double * len(prices))(*prices)
                return self._lib.compute_lyapunov_exponent(c_prices, len(prices), 5, 1)
            except Exception as e:
                logger.error(f"C++ LLE calculation failed: {e}")

        # Python fallback (simplified Rosenstein-like calculation)
        try:
            p = np.array(prices)
            diffs = np.abs(np.diff(np.log(p)))
            # Very crude approximation: if volatility is structured, LLE is higher
            return float(np.mean(diffs) / np.std(diffs)) if np.std(diffs) > 0 else 0.0
        except Exception as exc:
            logger.debug("ChaosAgent: Python LLE fallback failed: %s", exc)
            return 0.0

    async def inject_shadow_fault(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Injects artificial faults into shadow environment data streams (Non-destructive)."""
        import copy
        import random

        # GLOBAL PRODUCTION SAFEGUARD: Never inject faults in production
        if os.environ.get("SOVEREIGN_ENV") == "production":
            return data

        if random.random() < self.failure_prob:
            self.faults_injected += 1
            fault_type = random.choice(["DROP", "CORRUPT", "LATENCY"])

            if fault_type == "DROP":
                return None

            # Deep copy to ensure live data is not mutated
            faulty_data = copy.deepcopy(data)

            if fault_type == "CORRUPT" and "price" in faulty_data:
                faulty_data["price"] *= 1.0 + (random.random() - 0.5) * 0.1  # 5% corruption
                return faulty_data
            elif fault_type == "LATENCY":
                await asyncio.sleep(0.05)  # 50ms artificial lag
                return faulty_data

        return data
