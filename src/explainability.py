import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ExplainabilityEngine:
    """
    SHAP-inspired Explainable AI engine.
    Attributes trade decisions back to specific input features using
    Shapley value approximation via sampling-based marginal contribution.
    """

    def shapley_values(self, features: Dict[str, float], predict_fn, n_samples: int = 50) -> Dict[str, float]:
        import random
        feature_names = list(features.keys())
        shapley: Dict[str, float] = {k: 0.0 for k in feature_names}

        for _ in range(n_samples):
            perm = random.sample(feature_names, len(feature_names))
            coalition: Dict[str, float] = {}
            for feat in perm:
                without = predict_fn(coalition)
                coalition[feat] = features[feat]
                with_val = predict_fn(coalition)
                shapley[feat] += (with_val - without) / n_samples

        total = sum(abs(v) for v in shapley.values()) + 1e-9
        logger.info(f"[EXPLAIN] Top driver: {max(shapley, key=lambda k: abs(shapley[k]))}")
        return {k: round(v / total, 4) for k, v in shapley.items()}

    def generate_rationale(self, shapley: Dict[str, float], decision: str) -> str:
        top = sorted(shapley.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        reasons = [f"{k} ({v:+.1%})" for k, v in top]
        return f"Decision: {decision}. Driven by: {', '.join(reasons)}"
