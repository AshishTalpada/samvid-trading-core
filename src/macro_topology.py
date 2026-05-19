import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class MacroTopologyGraph:
    """
    Maps nth-degree macro ripple effects.
    e.g. "TSMC Earnings Miss" -> "Nvidia Drops" -> "S&P 500 Drops" -> "Volatility Spikes" -> "Bonds Rally".
    Calculates the shortest topological path between a breaking news event and an asset.
    """

    def __init__(self):
        self.nodes: Set[str] = set()
        self.adjacency: Dict[str, Dict[str, float]] = {}

    def add_link(self, source: str, target: str, impact_weight: float) -> None:
        self.nodes.add(source)
        self.nodes.add(target)
        if source not in self.adjacency:
            self.adjacency[source] = {}
        self.adjacency[source][target] = impact_weight

    def calculate_ripple_impact(
        self, event_node: str, target_asset: str, max_depth: int = 3
    ) -> float:
        if event_node not in self.adjacency:
            return 0.0

        # Dijkstra-style or DFS search for max impact path
        best_impact = 0.0

        def dfs(current: str, depth: int, current_impact: float):
            nonlocal best_impact
            if current == target_asset:
                best_impact = max(best_impact, current_impact)
                return
            if depth >= max_depth:
                return

            for neighbor, weight in self.adjacency.get(current, {}).items():
                dfs(neighbor, depth + 1, current_impact * weight)

        dfs(event_node, 0, 1.0)

        if best_impact > 0:
            logger.info(
                f"[TOPOLOGY] {event_node} -> {target_asset} ripple impact: {best_impact:.3f}"
            )

        return best_impact
