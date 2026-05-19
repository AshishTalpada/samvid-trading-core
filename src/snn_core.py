import logging

import numpy as np

logger = logging.getLogger(__name__)


class SpikingNeuralCore:
    """
    Core SNN processor using Exponential Integrate-and-Fire (EIF) neuron model.
    Extends basic LIF with an exponential spike upswing — matches real cortical neurons.
    Provides richer temporal coding for market microstructure signals.
    """

    def __init__(
        self, n: int = 256, tau_m: float = 20.0, delta_T: float = 2.0, theta_rh: float = -55.0
    ):
        self.n = n
        self.tau_m = tau_m
        self.delta_T = delta_T
        self.theta_rh = theta_rh  # Threshold rheobase
        self.V_thresh = -50.0
        self.V_reset = -70.0
        self.V_mem = np.full(n, self.V_reset)

    def step(self, I_ext: np.ndarray, dt: float = 0.1) -> np.ndarray:
        exp_term = self.delta_T * np.exp((self.V_mem - self.theta_rh) / self.delta_T)
        dV = dt / self.tau_m * (-self.V_mem + exp_term + I_ext)
        self.V_mem += dV
        spikes = self.V_mem >= self.V_thresh
        self.V_mem[spikes] = self.V_reset
        return spikes.astype(np.uint8)

    def run(self, input_current: np.ndarray, steps: int = 100, dt: float = 0.1) -> np.ndarray:
        spike_train = np.zeros((steps, self.n), dtype=np.uint8)
        for t in range(steps):
            I = input_current if input_current.ndim == 1 else input_current[t]
            spike_train[t] = self.step(I, dt)
        return spike_train

    def population_firing_rate(self, spike_train: np.ndarray) -> float:
        return float(spike_train.mean())
