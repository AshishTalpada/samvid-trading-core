from typing import Dict, List


class FeaturePruner:
    def __init__(self, threshold: float = 0.01):
        self.threshold = threshold

    def prune_features(self, feature_importances: Dict[str, float]) -> List[str]:
        return [f for f, imp in feature_importances.items() if imp > self.threshold]
