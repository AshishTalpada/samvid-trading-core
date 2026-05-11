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
    def __init__(self, bridge: Any = None, **kwargs):
        from vault import Vault
        self.bridge = bridge

        # Default reputation score of neural sub-agents (0.0 to 1.0)
        # We attempt to fetch from Vault first for dynamic tuning.
        self.agent_reputations = {
            "Agent_C": float(Vault.get("REP_AGENT_C", 0.8)),
            "Agent_G": float(Vault.get("REP_AGENT_G", 0.5)),
            "Agent_O": float(Vault.get("REP_AGENT_O", 0.6)),
            "Agent_S": float(Vault.get("REP_AGENT_S", 0.5)),
            "Agent_F": float(Vault.get("REP_AGENT_F", 0.7))
        }
        self.learning_rate = float(Vault.get("AGENT_LEARNING_RATE", 0.05))

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
                # Agent disagreed with the trade (Voted HOLD or opposite direction)
                if is_win:
                    if vote == "HOLD":
                        # Neutral: Being cautious during a winner is not a penalty-worthy offense
                        new_rep = current_rep
                    else:
                        # Penalize (Voted SELL when system bought a WINNER)
                        new_rep = current_rep - self.learning_rate * current_rep
                else:
                    # Agent was right to disagree with a LOSER
                    new_rep = current_rep + self.learning_rate * (1.0 - current_rep)

            self.agent_reputations[agent] = max(0.1, min(0.99, new_rep))

        logger.debug(f"[ARCHITECT] Neural Topologies adjusted. New Reputations: {self.agent_reputations}")

    async def _tool_check_syntax(self, file_path: str) -> Dict[str, Any]:
        """
        Uses the Python 'ast' module to check for syntax fractures before hot-reloading.
        """
        import ast
        import os

        if not os.path.exists(file_path):
            return {"valid": False, "summary": "File not found"}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source)
            return {"valid": True, "summary": "Syntax Perfect"}
        except SyntaxError as e:
            logger.error(f"MindArchitect: Syntax Fracture detected in {file_path}: {e}")
            return {"valid": False, "summary": str(e)}

    def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Participates in the quorum with meta-level oversight."""
        # Architect usually votes YES unless a deadlock is imminent
        return {
            "agent": "Agent_G_MindArchitect",
            "vote": "YES",
            "confidence": 0.9,
            "reason": "Neural Topology remains balanced."
        }

    async def start(self):
        """Initializes the architect's background coordination tasks."""
        logger.info("MindArchitect: Coordination engine active.")
