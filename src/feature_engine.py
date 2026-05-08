import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class RecursiveFeatureEliminator:
    """
    Automatically prunes irrelevant technical indicators using permutation importance.
    Prevents overfitting by eliminating features whose removal does not increase prediction error.
    """
    def compute_importance(self, X: np.ndarray, y: np.ndarray, model_predict) -> np.ndarray:
        baseline_error = float(np.mean((model_predict(X) - y) ** 2))
        importances = np.zeros(X.shape[1])
        for col in range(X.shape[1]):
            X_perm = X.copy()
            np.random.shuffle(X_perm[:, col])
            perm_error = float(np.mean((model_predict(X_perm) - y) ** 2))
            importances[col] = perm_error - baseline_error
        return importances

    def eliminate(self, feature_names: List[str], importances: np.ndarray, threshold: float = 0.0) -> List[str]:
        kept = [name for name, imp in zip(feature_names, importances, strict=False) if imp > threshold]
        removed = [name for name, imp in zip(feature_names, importances, strict=False) if imp <= threshold]
        if removed: logger.info(f"[FEATURE ENGINE] Pruned {len(removed)} features: {removed[:5]}...")
        return kept
