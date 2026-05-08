import numpy as np
import logging
logger = logging.getLogger(__name__)

class LiquidNeuralNet:
    """Continuous-time ODE-inspired adaptive network for volatile market reasoning."""
    def __init__(self, n_neurons: int = 16, tau: float = 1.0):
        self.n = n_neurons
        self.tau = tau
        self.state = np.zeros(n_neurons)
        self.W = np.random.randn(n_neurons, n_neurons) * 0.1

    def step(self, inputs: np.ndarray, dt: float = 0.1) -> np.ndarray:
        dx = (-self.state + np.tanh(self.W @ self.state + inputs[:self.n])) / self.tau
        self.state = self.state + dt * dx
        return self.state.copy()

    def predict(self, inputs: list[float]) -> float:
        out = self.step(np.array(inputs))
        return float(np.mean(out))
