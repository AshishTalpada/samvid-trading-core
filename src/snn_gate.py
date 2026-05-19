import logging

import numpy as np

logger = logging.getLogger(__name__)


class LeakyIntegrateFireGate:
    """
    Spiking Neural Network gate using LIF neuron model.
    Fires a spike (trade signal) only when membrane potential crosses threshold.
    Bio-inspired: mimics how biological neurons filter noise from signal.
    """

    def __init__(self, threshold: float = 1.0, tau: float = 20.0, dt: float = 1.0):
        self.V_thresh = threshold
        self.tau = tau
        self.dt = dt
        self.V_mem = 0.0

    def step(self, current_input: float) -> bool:
        """Returns True if neuron fires (trade signal)."""
        dV = (-self.V_mem + current_input) / self.tau * self.dt
        self.V_mem += dV
        if self.V_mem >= self.V_thresh:
            self.V_mem = 0.0
            return True
        return False

    def process_stream(self, inputs: list[float]) -> list[int]:
        return [1 if self.step(x) else 0 for x in inputs]
