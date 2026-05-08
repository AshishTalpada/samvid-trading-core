import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class MindArchitect:
    '''
    Deep Dive: The Meta-Agent (The Brain of Brains).
    Orchestrates the entire neural quorum. It routes standard decisions to the Voting System,
    experimental signals to the Ghost Environment, and tie-breakers to the Ultrathink engine.
    It actively alters the weights of sub-agents based on their historical accuracy.
    '''
    def __init__(self):
        # The reputation score of every neural sub-agent (0.0 to 1.0)
        self.agent_reputations = {
            "AgentC_MT5": 0.8,
            "AgentG_GNN": 0.5,
            "AgentO_ODE": 0.6,
            "AgentS_Sentiment": 0.5
        }
        self.learning_rate = 0.05

    def request_quorum_decision(self, agent_votes: Dict[str, str], confidences: Dict[str, float]) -> Dict[str, Any]:
        '''
        Calculates a reputation-weighted consensus.
        If an agent has a history of being wrong, its vote is mathematically suppressed.
        '''
        buy_weight = 0.0
        sell_weight = 0.0
        hold_weight = 0.0

        for agent, vote in agent_votes.items():
            rep = self.agent_reputations.get(agent, 0.5)
            conf = confidences.get(agent, 0.5)

            # Final vote power = Reputation * Confidence
            power = rep * conf

            if vote == "BUY":
                buy_weight += power
            elif vote == "SELL":
                sell_weight += power
            else:
                hold_weight += power

        total_power = buy_weight + sell_weight + hold_weight
        if total_power == 0:
            return {"decision": "HOLD", "conviction": 0.0, "is_deadlock": False}

        buy_pct = buy_weight / total_power
        sell_pct = sell_weight / total_power

        # If no clear majority (e.g., Buy and Sell are within 10% of each other), flag as Deadlock
        if abs(buy_pct - sell_pct) < 0.10 and (buy_pct > 0.3):
            logger.warning("[ARCHITECT] Quorum Deadlock detected. Routing to Ultrathink.")
            return {"decision": "DEADLOCK", "conviction": 0.0, "is_deadlock": True}

        if buy_pct > max(sell_pct, 0.4): # Threshold to act
            return {"decision": "BUY", "conviction": buy_pct, "is_deadlock": False}
        elif sell_pct > max(buy_pct, 0.4):
            return {"decision": "SELL", "conviction": sell_pct, "is_deadlock": False}

        return {"decision": "HOLD", "conviction": hold_weight / total_power, "is_deadlock": False}

    def penalize_or_reward_agents(self, trade_result_pnl: float, original_votes: Dict[str, str], executed_action: str):
        '''
        Reinforcement Learning step. Adjusts the reputation of sub-agents post-trade.
        '''
        is_win = trade_result_pnl > 0

        for agent, vote in original_votes.items():
            current_rep = self.agent_reputations.get(agent, 0.5)

            if vote == executed_action:
                # Agent agreed with the trade
                if is_win:
                    new_rep = current_rep + self.learning_rate * (1.0 - current_rep) # Reward
                else:
                    new_rep = current_rep - self.learning_rate * current_rep # Penalize
            else:
                # Agent disagreed with the trade
                if is_win:
                    new_rep = current_rep - self.learning_rate * current_rep # Penalize (missed out)
                else:
                    new_rep = current_rep + self.learning_rate * (1.0 - current_rep) # Reward (saved us)

            self.agent_reputations[agent] = max(0.1, min(0.99, new_rep))

        logger.debug(f"[ARCHITECT] Neural Topologies adjusted. New Reputations: {self.agent_reputations}")
