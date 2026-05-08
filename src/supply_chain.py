import logging
from collections import deque

logger = logging.getLogger(__name__)

class SupplyChainGraph:
    """
    Directed Graph tracking tier-N supply chain relationships.
    Tracks how events in one region cascade to correlated assets.
    """
    def __init__(self):
        # node -> [(target_node, impact_weight)]
        self.graph = {}
        
    def add_link(self, supplier: str, consumer: str, dependency_weight: float):
        if supplier not in self.graph:
            self.graph[supplier] = []
        self.graph[supplier].append((consumer, dependency_weight))

    def evaluate_impact(self, origin_event_node: str, shock_magnitude: float) -> dict[str, float]:
        """
        Uses Breadth-First Search (BFS) to cascade a shock through the supply chain graph.
        Returns a dictionary of all affected nodes and their resulting impact.
        """
        impacts = {origin_event_node: shock_magnitude}
        queue = deque([(origin_event_node, shock_magnitude)])
        
        while queue:
            current_node, current_shock = queue.popleft()
            
            # Attenuate shock if it gets too small
            if abs(current_shock) < 0.01:
                continue
                
            if current_node in self.graph:
                for consumer, weight in self.graph[current_node]:
                    transmitted_shock = current_shock * weight
                    
                    if consumer in impacts:
                        impacts[consumer] += transmitted_shock
                    else:
                        impacts[consumer] = transmitted_shock
                        
                    queue.append((consumer, transmitted_shock))
                    
        return impacts
