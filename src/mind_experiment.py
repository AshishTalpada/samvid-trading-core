import copy
import logging
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class EvolutionaryNeuroExperiment:
    '''
    Autonomous Neuro-Evolution Engine.
    When Sovereign detects alpha decay in a specific neural agent, this module
    spawns N mutated clones of the failing agent, tweaks their hyperparameters
    (simulated via genetic algorithms), and runs them in a shadow (paper) environment
    to "breed" a stronger, adapted successor model.
    '''
    def __init__(self, population_size: int = 20, mutation_rate: float = 0.15, **kwargs):
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.population: Any = []
        self.generation = 1

    def init_population(self, base_weights: np.ndarray):
        '''Creates the initial mutated swarm of clones.'''
        self.population = []
        for _ in range(self.pop_size):
            # Apply Gaussian noise mutation
            noise = np.random.normal(loc=0.0, scale=self.mutation_rate, size=base_weights.shape)
            clone = base_weights + noise
            self.population.append({"weights": clone, "fitness": 0.0})
        logger.info(f"[EVOLUTION] Generation {self.generation} spawned with {self.pop_size} clones.")

    def evaluate_fitness(self, market_data: np.ndarray, target_labels: np.ndarray):
        '''Simulates paper-trading the clones over historical data to score them.'''
        if not self.population:
            return

        for clone in self.population:
            try:
                # Shape validation
                if market_data.shape[1] != clone["weights"].shape[0]:
                    logger.error(f"[EVOLUTION] Shape mismatch: Data {market_data.shape} vs Weights {clone['weights'].shape}")
                    clone["fitness"] = 0.0
                    continue

                # Simplified proxy for neural network forward pass (Linear regression style)
                predictions = np.dot(market_data, clone["weights"])

                # Handle potential NaNs from np.dot
                if np.any(np.isnan(predictions)):
                    clone["fitness"] = 0.0
                    continue

                # Mean Squared Error as inverse fitness with Log-Scaling for stability
                mse = float(np.mean((predictions - target_labels) ** 2))

                if np.isnan(mse) or np.isinf(mse):
                    clone["fitness"] = 0.0
                else:
                    # Log-scaling prevents fitness explosion and improves selection pressure
                    clone["fitness"] = 1.0 / (1.0 + np.log1p(mse))
            except Exception as e:
                logger.error(f"[EVOLUTION] Fitness calculation failed: {e}")
                clone["fitness"] = 0.0

        # Sort population by fitness descending
        self.population.sort(key=lambda x: x['fitness'], reverse=True)
        best_fitness = self.population[0]['fitness']
        logger.info(f"[EVOLUTION] Gen {self.generation} evaluated. Top Fitness: {best_fitness:.4f}")

    def breed_next_generation(self) -> np.ndarray:
        '''
        Takes the top 20% of clones and uses crossover/mutation to spawn the next generation.
        Returns the current Apex (best) weights.
        '''
        if not self.population:
            return np.array([])

        top_percentile = max(2, int(self.pop_size * 0.2))
        elites = self.population[:top_percentile]

        new_population = copy.deepcopy(elites) # Keep elites intact

        # Fill the rest of the population with crossover and mutation
        while len(new_population) < self.pop_size:
            # Randomly select two parents from the elite pool
            p1 = elites[np.random.randint(0, len(elites))]['weights']
            p2 = elites[np.random.randint(0, len(elites))]['weights']

            # Crossover (50/50 mix)
            mask = np.random.rand(*p1.shape) > 0.5
            child_weights = np.where(mask, p1, p2)

            # Mutation with clipping to prevent numerical explosion
            noise = np.random.normal(loc=0.0, scale=self.mutation_rate, size=child_weights.shape)
            child_weights += noise

            # Absolute limit on weight drift to maintain structural integrity
            child_weights = np.clip(child_weights, -10.0, 10.0)

            new_population.append({"weights": child_weights, "fitness": 0.0})

        self.population = new_population
        self.generation += 1

        return elites[0]['weights']  # type: ignore

    async def start(self):
        """Initializes the evolutionary neuro-experiment suite."""
        logger.info("MindExperiment: Evolutionary simulation environment online.")

MindExperiment = EvolutionaryNeuroExperiment
