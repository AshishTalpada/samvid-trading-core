import numpy as np

class SpikingNetwork:
    def __init__(self, n_neurons: int = 100):
        self.n = n_neurons
        self.v = np.zeros(n_neurons)

    def integrate_and_fire(self, spikes: np.ndarray, threshold: float = 1.0) -> np.ndarray:
        self.v += spikes
        fired = self.v >= threshold
        self.v[fired] = 0.0
        return fired
