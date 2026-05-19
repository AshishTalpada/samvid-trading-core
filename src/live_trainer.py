import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class OnlineLiveTrainer:
    """
    Real-time online learning loop. Updates agent weights immediately after
    every closed trade, effectively giving the Sovereign System a learning rate
    that compounds on every single execution (The Singularity engine driver).
    """

    def __init__(self, learning_rate: float = 0.001):
        self.lr = learning_rate
        self.agent_weights: Dict[str, float] = {}

    def register_agent(self, agent_name: str, initial_weight: float = 1.0) -> None:
        self.agent_weights[agent_name] = initial_weight

    def update_from_trade(self, trade_pnl_pct: float, agent_votes: Dict[str, float]) -> None:
        if not agent_votes:
            return

        # Positive PNL rewards agents proportional to their conviction.
        # Negative PNL punishes them.
        reward = trade_pnl_pct * 100.0  # Scale up for weight update

        for agent, vote_conviction in agent_votes.items():
            if agent not in self.agent_weights:
                self.register_agent(agent)

            # Gradient update step
            update = self.lr * reward * vote_conviction
            self.agent_weights[agent] += update

            # Bound weights
            self.agent_weights[agent] = max(0.1, min(5.0, self.agent_weights[agent]))

        logger.info(f"[LIVE TRAINER] Updated weights after trade (PNL: {trade_pnl_pct:.2%})")

    def get_weights(self) -> Dict[str, float]:
        return self.agent_weights
