import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class RegimeAttentionEngine:
    """
    Dynamically "attends" to historical market regimes that match current conditions.
    When current price structure matches 2008-style correlations, the engine
    upweights lessons from that period in all agent decisions.
    """

    REGIME_FINGERPRINTS: Dict[str, Dict[str, float]] = {
        "2008_GFC":     {"vol": 0.9, "credit_spread": 0.9, "correlation": 0.95},
        "2020_COVID":   {"vol": 0.8, "credit_spread": 0.6, "correlation": 0.85},
        "2000_DOTCOM":  {"vol": 0.7, "credit_spread": 0.3, "correlation": 0.4},
        "2022_RATES":   {"vol": 0.5, "credit_spread": 0.5, "correlation": 0.6},
        "NORMAL_BULL":  {"vol": 0.2, "credit_spread": 0.1, "correlation": 0.3},
    }

    def compute_attention(self, current: Dict[str, float]) -> Dict[str, float]:
        keys = list(current.keys())
        weights: Dict[str, float] = {}
        for name, fingerprint in self.REGIME_FINGERPRINTS.items():
            c = np.array([current.get(k, 0.0) for k in keys])
            f = np.array([fingerprint.get(k, 0.0) for k in keys])
            dist = float(np.linalg.norm(c - f))
            weights[name] = 1.0 / (dist + 0.1)
        total = sum(weights.values())
        normalised = {k: round(v / total, 4) for k, v in weights.items()}
        top = max(normalised, key=normalised.get)  # type: ignore
        logger.info(f"[ATTENTION] Closest regime: '{top}' ({normalised[top]:.0%} weight)")
        return normalised
