import logging

import numpy as np

logger = logging.getLogger(__name__)

class SpikingNeuralInference:
    """
    Bio-inspired Spiking Neural Network inference gate.
    Uses Leaky Integrate-and-Fire (LIF) population coding to convert
    continuous market signals into discrete spike trains for ultrafast decisions.
    """
    def __init__(self, n_neurons: int = 100, tau: float = 20.0, threshold: float = 1.0):
        self.n = n_neurons
        self.tau = tau
        self.V_thresh = threshold
        rng = np.random.default_rng(42)
        self.tuning_centers = rng.uniform(-1, 1, n_neurons)
        self.V_mem = np.zeros(n_neurons)

    def encode(self, signal: float) -> np.ndarray:
        tuning = np.exp(-0.5 * ((signal - self.tuning_centers) / 0.2) ** 2)
        return tuning

    def step(self, signal: float, dt: float = 1.0) -> np.ndarray:
        current = self.encode(signal)
        dV = (-self.V_mem + current) / self.tau * dt
        self.V_mem += dV
        spikes = self.V_mem >= self.V_thresh
        self.V_mem[spikes] = 0.0
        return spikes.astype(np.uint8)

    def infer(self, signal_series: list[float]) -> str:
        spike_counts = np.zeros(self.n)
        for s in signal_series:
            spike_counts += self.step(s)
        total = spike_counts.sum()
        if total == 0: return "HOLD"
        positive_side = spike_counts[self.tuning_centers > 0].sum()
        negative_side = spike_counts[self.tuning_centers < 0].sum()
        if positive_side > negative_side * 1.3: return "BUY"
        if negative_side > positive_side * 1.3: return "SELL"
        return "HOLD"
