import logging
import math
import random
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


class QuantumInspiredOptimizer:
    """
    Quantum-Inspired Simulated Annealing (QISA).
    Uses quantum tunnelling probability to escape local optima — the parameter
    can "tunnel through" a bad valley even when the hill is too high to climb classically.

    Inspired by: Finnila et al. (1994) "Quantum Annealing"
    """

    def __init__(
        self,
        objective: Callable[[np.ndarray], float],
        bounds: list[tuple[float, float]],
        tunneling_strength: float = 0.5,
        n_steps: int = 5000,
        initial_temp: float = 1.0,
        cooling_rate: float = 0.995,
    ) -> None:
        self.objective = objective
        self.bounds = np.array(bounds)
        self.gamma = tunneling_strength  # Quantum tunneling coefficient Γ
        self.n_steps = n_steps
        self.T0 = initial_temp
        self.cooling = cooling_rate
        self.dim = len(bounds)

    def _quantum_tunnel_prob(self, delta_e: float, temp: float, gamma: float) -> float:
        """
        P(tunnel) = exp(-|ΔE| / (ℏ * Γ)) where Γ is the transverse field strength.
        In classical simulated annealing P = exp(-ΔE / kT).
        The quantum term adds an extra tunneling path bypassing energy barriers.
        """
        classical = math.exp(-abs(delta_e) / max(temp, 1e-9))
        quantum_boost = math.exp(-abs(delta_e) / max(gamma, 1e-9))
        return max(classical, quantum_boost)

    def run(self) -> tuple[np.ndarray, float]:
        lo, hi = self.bounds[:, 0], self.bounds[:, 1]
        current = lo + np.random.rand(self.dim) * (hi - lo)
        current_score = self.objective(current)
        best = current.copy()
        best_score = current_score
        T = self.T0

        for step in range(self.n_steps):
            # Proposal: Gaussian perturbation scaled to bounds range
            proposal = current + np.random.randn(self.dim) * (hi - lo) * 0.05
            proposal = np.clip(proposal, lo, hi)
            proposal_score = self.objective(proposal)
            delta = proposal_score - current_score

            if delta < 0 or random.random() < self._quantum_tunnel_prob(delta, T, self.gamma):
                current = proposal
                current_score = proposal_score
                if current_score < best_score:
                    best = current.copy()
                    best_score = current_score

            T *= self.cooling

            if step % 500 == 0:
                logger.debug(f"[QISA] Step {step} | T={T:.4f} | Best={best_score:.6f}")

        logger.info(f"[QISA] Optimization complete. Best score: {best_score:.6f}")
        return best, best_score
