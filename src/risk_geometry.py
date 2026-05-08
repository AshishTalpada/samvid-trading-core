import numpy as np

class HyperbolicRisk:
    def __init__(self, curvature: float = -1.0):
        self.curvature = curvature

    def calculate_distance(self, p1: float, p2: float) -> float:
        delta = abs(p1 - p2)
        return float(np.arccosh(1 + 2 * (delta**2) / ((1 - p1**2) * (1 - p2**2) + 1e-9)))
