import numpy as np


class EntropySizer:
    """
    Position sizing based on Shannon Entropy (surprise/uncertainty).
    """

    def calculate_position_size(
        self, probabilities: list[float], max_risk_pct: float = 0.02
    ) -> float:
        """
        Shannon Entropy based position sizing.
        High entropy = high uncertainty = lower size.

        Args:
            probabilities: The probability distribution of expected outcomes.
            max_risk_pct: Maximum risk allowed per trade (e.g., 0.02 for 2%).

        Returns:
            Adjusted position risk percentage.
        """
        if not probabilities:
            return 0.0

        p = np.array(probabilities, dtype=float)
        total = np.sum(p)
        if total <= 0:
            return 0.0
        # Normalize and clip to avoid log(0)
        p = p / total
        p = np.clip(p, 1e-9, 1 - 1e-9)

        # Shannon entropy
        entropy = -np.sum(p * np.log2(p))

        # Max entropy for N outcomes is log2(N)
        max_entropy = np.log2(len(p)) if len(p) > 1 else 1.0

        # Normalized uncertainty (0 to 1)
        uncertainty = entropy / max_entropy if max_entropy > 0 else 0

        # Confidence is the inverse of uncertainty
        confidence = 1.0 - uncertainty

        # Scale max risk by confidence
        return max_risk_pct * confidence
