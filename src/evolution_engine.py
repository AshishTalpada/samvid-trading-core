import logging
import math
import random
from typing import Callable

import numpy as np

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Differential Evolution optimizer for continuous hyperparameter search.
    Outperforms vanilla genetic algorithms on ill-conditioned loss surfaces
    by using vector differences of population members to generate new candidates.
    """

    def __init__(
        self,
        objective: Callable[[np.ndarray], float],
        bounds: list[tuple[float, float]],
        population_size: int = 20,
        mutation_factor: float = 0.8,
        crossover_prob: float = 0.7,
        max_generations: int = 100,
    ) -> None:
        self.objective = objective
        self.bounds = np.array(bounds)
        self.pop_size = population_size
        self.F = mutation_factor
        self.CR = crossover_prob
        self.max_gen = max_generations
        self.dim = len(bounds)

    def _init_population(self) -> np.ndarray:
        lo = self.bounds[:, 0]
        hi = self.bounds[:, 1]
        return lo + np.random.rand(self.pop_size, self.dim) * (hi - lo)

    def run(self) -> tuple[np.ndarray, float]:
        """
        Runs Differential Evolution.
        Returns (best_params, best_score).
        """
        pop = self._init_population()
        fitness = np.array([self.objective(ind) for ind in pop])
        best_idx = int(np.argmin(fitness))
        best = pop[best_idx].copy()
        best_score = float(fitness[best_idx])

        for gen in range(self.max_gen):
            for i in range(self.pop_size):
                # Select 3 distinct random indices (not i)
                candidates = [j for j in range(self.pop_size) if j != i]
                a, b, c = random.sample(candidates, 3)

                # Mutation: V = pop[a] + F * (pop[b] - pop[c])
                mutant = pop[a] + self.F * (pop[b] - pop[c])

                # Clip to bounds
                lo, hi = self.bounds[:, 0], self.bounds[:, 1]
                mutant = np.clip(mutant, lo, hi)

                # Crossover
                cross_mask = np.random.rand(self.dim) < self.CR
                if not np.any(cross_mask):
                    cross_mask[random.randint(0, self.dim - 1)] = True

                trial = np.where(cross_mask, mutant, pop[i])

                # Selection
                trial_score = self.objective(trial)
                if trial_score <= fitness[i]:
                    pop[i] = trial
                    fitness[i] = trial_score
                    if trial_score < best_score:
                        best = trial.copy()
                        best_score = trial_score

            if gen % 10 == 0:
                logger.debug(f"[EVOLUTION] Gen {gen}/{self.max_gen} | Best: {best_score:.6f}")

        logger.info(f"[EVOLUTION] Completed. Best score: {best_score:.6f}")
        return best, best_score
