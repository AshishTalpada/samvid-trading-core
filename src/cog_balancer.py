import logging
import statistics
from typing import Dict, List

logger = logging.getLogger(__name__)


class CognitiveLoadBalancer:
    """
    Balances cognitive workload across reasoning agents to prevent bottlenecks.
    Tracks per-agent response latency and re-routes overflow to faster agents.
    Inspired by NUMA-aware memory allocation for AI inference.
    """

    def __init__(self):
        self._latencies: Dict[str, List[float]] = {}

    def record_latency(self, agent_id: str, latency_ms: float) -> None:
        if agent_id not in self._latencies:
            self._latencies[agent_id] = []
        self._latencies[agent_id].append(latency_ms)
        if len(self._latencies[agent_id]) > 100:
            self._latencies[agent_id].pop(0)

    def agent_load_score(self, agent_id: str) -> float:
        lats = self._latencies.get(agent_id, [])
        return statistics.mean(lats[-10:]) if len(lats) >= 2 else 0.0

    def fastest_agent(self) -> str | None:
        if not self._latencies:
            return None
        return min(self._latencies, key=lambda aid: self.agent_load_score(aid))

    def rebalance_assignments(self, task_agents: List[str]) -> List[str]:
        scores = {a: self.agent_load_score(a) for a in task_agents}
        rebalanced = sorted(task_agents, key=lambda a: scores.get(a, 0))
        logger.debug(f"[COG BALANCER] Rebalanced: {rebalanced[:3]}")
        return rebalanced
