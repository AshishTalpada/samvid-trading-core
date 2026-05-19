import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class MacroKnowledgeGraph:
    """
    Connects macro events (e.g. Fed Rate hike) to specific equity sectors.
    Uses an in-memory directed graph to traverse "Event -> Sector -> Ticker"
    relationships to instantly map the blast radius of breaking news.
    """

    def __init__(self):
        self.edges: Dict[str, Set[str]] = {}

    def add_relation(self, source: str, target: str) -> None:
        if source not in self.edges:
            self.edges[source] = set()
        self.edges[source].add(target)

    def traverse(self, root_event: str, depth: int = 2) -> List[str]:
        visited = set()
        queue = [(root_event, 0)]
        impacted_nodes = []

        while queue:
            current, current_depth = queue.pop(0)
            if current_depth > depth:
                break

            if current not in visited:
                visited.add(current)
                if current != root_event:
                    impacted_nodes.append(current)

                for neighbor in self.edges.get(current, []):
                    if neighbor not in visited:
                        queue.append((neighbor, current_depth + 1))

        logger.debug(
            f"[KG] Event '{root_event}' impacts {len(impacted_nodes)} nodes at depth {depth}."
        )
        return impacted_nodes
