import logging

import numpy as np

logger = logging.getLogger(__name__)


class LiquidNeuralCore:
    """
    Continuous-time ODE Liquid Neural Network core for fluid reasoning.
    Adjusts its internal time-constants dynamically based on market volatility,
    allowing it to sample faster during chaos and slower during consolidation.
    """

    def __init__(self, hidden_dim: int = 64):
        self.hidden_dim = hidden_dim
        self.state = np.zeros(hidden_dim)
        # Random initialized weights for continuous time updates
        self.w_in = np.random.randn(hidden_dim, 10) * 0.1
        self.w_rec = np.random.randn(hidden_dim, hidden_dim) * 0.1
        self.time_constant = np.ones(hidden_dim) * 0.5

    def step(self, x: np.ndarray, dt: float, volatility: float) -> np.ndarray:
        # Dynamic time constant based on volatility
        # High volatility -> shorter time constants -> faster adaptation
        tau = self.time_constant / (1.0 + volatility * 5.0)

        # Continuous time ODE step approximation (Euler method)
        dx = -self.state / tau + np.tanh(np.dot(self.w_in, x) + np.dot(self.w_rec, self.state))
        self.state += dx * dt

        return self.state

    def reset(self) -> None:
        self.state = np.zeros(self.hidden_dim)
        logger.debug("[LIQUID CORE] State reset to zero.")
