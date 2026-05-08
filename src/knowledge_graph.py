from typing import Dict, Set

class KnowledgeGraph:
    """Models relationships between macro events and asset sectors."""
    def __init__(self):
        self.edges: Dict[str, Set[str]] = {}

    def add_relationship(self, cause: str, effect: str) -> None:
        self.edges.setdefault(cause, set()).add(effect)

    def get_ripple_effects(self, event: str, depth: int = 2) -> Set[str]:
        visited: Set[str] = set()
        frontier = {event}
        for _ in range(depth):
            next_frontier: Set[str] = set()
            for node in frontier:
                for neighbor in self.edges.get(node, set()):
                    if neighbor not in visited:
                        next_frontier.add(neighbor)
                        visited.add(neighbor)
            frontier = next_frontier
        return visited
