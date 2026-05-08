import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class RLHFOnlineTrainer:
    """
    Reinforcement Learning from Human Feedback (RLHF) online trainer.
    Collects operator feedback on trade decisions (thumbs up/down) and
    uses it to update agent preference weights via DPO (Direct Preference Optimisation).
    """

    def __init__(self, feedback_path: str = "data/rlhf_feedback.jsonl"):
        self._path = Path(feedback_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._preferences: list[dict] = []
        self._agent_scores: Dict[str, float] = {}

    def record_feedback(self, decision_id: str, agents_voted_yes: List[str],
                        agents_voted_no: List[str], outcome: str, human_rating: float) -> None:
        entry = {
            "decision_id": decision_id, "yes_agents": agents_voted_yes,
            "no_agents": agents_voted_no, "outcome": outcome,
            "human_rating": human_rating,  # -1.0 (terrible) to +1.0 (excellent)
        }
        self._preferences.append(entry)
        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self._update_scores(entry)
        logger.info(f"[RLHF] Feedback recorded: {decision_id} rating={human_rating:+.1f}")

    def _update_scores(self, entry: dict) -> None:
        lr = 0.05
        reward = entry["human_rating"]
        for agent in entry.get("yes_agents", []):
            self._agent_scores[agent] = self._agent_scores.get(agent, 1.0) + lr * reward
        for agent in entry.get("no_agents", []):
            self._agent_scores[agent] = self._agent_scores.get(agent, 1.0) - lr * reward * 0.5

    def get_agent_preference_weight(self, agent_id: str) -> float:
        raw = self._agent_scores.get(agent_id, 1.0)
        return max(0.1, min(3.0, raw))

    def top_agents(self, n: int = 5) -> List[tuple[str, float]]:
        return sorted(self._agent_scores.items(), key=lambda x: x[1], reverse=True)[:n]
