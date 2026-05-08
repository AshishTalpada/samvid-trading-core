from typing import Dict

class NetworkPathfinder:
    """Routes network packets via the lowest latency path based on physical proximity."""
    def __init__(self, route_latencies_ms: Dict[str, float]):
        self.routes = route_latencies_ms

    def best_route(self) -> str:
        if not self.routes:
            return "default"
        return min(self.routes, key=lambda k: self.routes[k])

    def update_latency(self, route: str, latency_ms: float) -> None:
        self.routes[route] = latency_ms
