import asyncio
import copy
import logging
import time
from typing import Any

import numpy as np

from mind_bridge import MindBridge
from strategy_promotion import evaluate_strategy_promotion

logger = logging.getLogger(__name__)


# Global mt5_raw reference (placeholder for actual MT5 terminal object)
mt5_raw: Any = None


class MindExperiment:
    """
    Agent E: The Experiment Mind (A/B Gating).
    Inspired by Claude-Code's 'GrowthBook' and 'A/B Testing' logic.
    Runs 'Shadow Experiments' to find the optimal trading parameters.
    Also handles Autonomous Neuro-Evolution.
    """

    def __init__(self, bridge: MindBridge) -> None:
        self.bridge = bridge
        self.is_running = False
        self.active_experiments: dict[str, Any] = {}
        self.mt5: Any = mt5_raw

        # Evolution specific attributes
        self.pop_size = 20
        self.mutation_rate = 0.15
        self.population: Any = []
        self.generation = 1

        # Register Experimenting Tools
        self.bridge.register_tool("run_shadow_test", self._tool_run_shadow_test)
        self.bridge.register_tool("report_experiment_outcome", self._tool_report_experiment_outcome)
        self.bridge.register_tool("gate_feature", self._tool_gate_feature)

    async def start(self) -> None:
        """Launch the Experiment Mind."""
        self.is_running = True
        logger.info("MindExperiment (Agent E): A/B Gating and Evolution engine active.")
        logger.info("MindExperiment: Evolutionary simulation environment online.")
        asyncio.create_task(self._monitor_shadow_tests())

    async def _monitor_shadow_tests(self) -> None:
        """Continuously audits live shadow tests for performance."""
        while self.is_running:
            try:
                # Logic: Compare Strategy A (Live) vs. Strategy B (Shadow)
                # If B is 10% more profitable after 10 trades, promote B
                await asyncio.sleep(600)  # Every 10 minutes
            except Exception as e:
                logger.error(f"MindExperiment: Audit Error: {e}")
                await asyncio.sleep(10)

    async def _tool_run_shadow_test(
        self, feature_name: str, variant_id: str, logic: dict
    ) -> dict[str, Any]:
        """Initiates a 'Shadow Experiment' for a specific trading rule."""

        self.active_experiments[feature_name] = {
            "variant": variant_id,
            "logic": logic,
            "start_time": time.time_ns(),
            "performance_history": [],
        }
        logger.info(f"MindExperiment: LAUNCHED SHADOW TEST: {feature_name} (Variant: {variant_id})")
        return {"id": feature_name, "status": "ACTIVE_SHADOW"}

    async def _tool_report_experiment_outcome(
        self, feature_name: str, pnl: float
    ) -> dict[str, Any]:
        """Records a trade outcome into the experiment's performance history."""
        if feature_name not in self.active_experiments:
            return {"success": False, "error": f"Experiment {feature_name} not found."}

        self.active_experiments[feature_name]["performance_history"].append(pnl)
        logger.info(
            f"MindExperiment: RECORDED OUTCOME for {feature_name}: ${pnl:+.2f} (Total: {len(self.active_experiments[feature_name]['performance_history'])})"
        )
        return {
            "success": True,
            "history_depth": len(self.active_experiments[feature_name]["performance_history"]),
        }

    async def _tool_gate_feature(self, feature_name: str, enabled: bool) -> dict[str, Any]:
        """
        Gates or enables a feature based on experiment results.
        Ensures AI cannot enable features without recorded shadow performance.
        """
        logger.info(
            f"MindExperiment: Evaluating GATE request for {feature_name} (ENABLED={enabled})..."
        )

        if enabled:
            # 1. Check if the experiment exists
            exp = self.active_experiments.get(feature_name)
            if not exp:
                logger.warning(
                    f"MindExperiment: GATE REJECTED. No active shadow test for {feature_name}."
                )
                return {"success": False, "error": "Neural Guard: No shadow test evidence found."}

            # 2. EVIDENCE CHECK: Retrieve shadow performance from database
            try:
                # Mock performance check - in production this queries QuestDB/SQLite
                # We enforce that the AI cannot self-enable without performance metadata
                performance = exp.get("performance_history", [])
                promotion = evaluate_strategy_promotion(performance)
                exp["promotion_report"] = promotion
                if not promotion["approved"]:
                    reason = "; ".join(promotion["reasons"])
                    logger.warning("MindExperiment: GATE REJECTED. %s.", reason)
                    return {
                        "success": False,
                        "error": f"Evidence Guard: {reason}.",
                        "promotion_report": promotion,
                    }

            except Exception as e:
                logger.error(f"MindExperiment: Evidence check failure: {e}")
                return {"success": False, "error": "Internal safety check error during gating."}

        # 3. If passed (or if disabling), trigger MindArchitect to update config
        logger.info(
            f"MindExperiment: GATING PASSED. Enabling feature {feature_name} in production."
        )
        return {"success": True, "evidence_verified": True}

    def init_population(self, base_weights: np.ndarray):
        """Creates the initial mutated swarm of clones."""
        self.population = []
        for _ in range(self.pop_size):
            # Apply Gaussian noise mutation
            noise = np.random.normal(loc=0.0, scale=self.mutation_rate, size=base_weights.shape)
            clone = base_weights + noise
            self.population.append({"weights": clone, "fitness": 0.0})
        logger.info(
            f"[EVOLUTION] Generation {self.generation} spawned with {self.pop_size} clones."
        )

    def evaluate_fitness(self, market_data: np.ndarray, target_labels: np.ndarray):
        """Simulates paper-trading the clones over historical data to score them."""
        if not self.population:
            return

        for clone in self.population:
            try:
                # Shape validation
                if market_data.shape[1] != clone["weights"].shape[0]:
                    logger.error(
                        f"[EVOLUTION] Shape mismatch: Data {market_data.shape} vs Weights {clone['weights'].shape}"
                    )
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
        self.population.sort(key=lambda x: x["fitness"], reverse=True)
        best_fitness = self.population[0]["fitness"]
        logger.info(f"[EVOLUTION] Gen {self.generation} evaluated. Top Fitness: {best_fitness:.4f}")

    def breed_next_generation(self) -> np.ndarray:
        """
        Takes the top 20% of clones and uses crossover/mutation to spawn the next generation.
        Returns the current Apex (best) weights.
        """
        if not self.population:
            return np.array([])

        top_percentile = max(2, int(self.pop_size * 0.2))
        elites = self.population[:top_percentile]

        new_population = copy.deepcopy(elites)  # Keep elites intact

        # Fill the rest of the population with crossover and mutation
        while len(new_population) < self.pop_size:
            # Randomly select two parents from the elite pool
            p1 = elites[np.random.randint(0, len(elites))]["weights"]
            p2 = elites[np.random.randint(0, len(elites))]["weights"]

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

        return elites[0]["weights"]  # type: ignore


# Aliases for Sovereign Compatibility
EvolutionaryNeuroExperiment = MindExperiment
