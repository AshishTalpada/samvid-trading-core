import logging
import socket
import time
from typing import List, Tuple

logger = logging.getLogger(__name__)

class FiberPathfinder:
    """
    Routes network packets over the physically fastest path based on speed-of-light propagation.
    Measures TCP RTT to each route endpoint and selects the minimum latency path.
    """
    def probe_latency(self, host: str, port: int = 80, samples: int = 5) -> float:
        latencies = []
        for _ in range(samples):
            try:
                t0 = time.perf_counter()
                s = socket.create_connection((host, port), timeout=0.5)
                s.close()
                latencies.append(time.perf_counter() - t0)
            except OSError:
                latencies.append(float("inf"))
        finite = [l for l in latencies if l != float("inf")]
        return min(finite) if finite else float("inf")

    def select_fastest(self, routes: List[Tuple[str, int]]) -> Tuple[str, int]:
        best_route = routes[0]
        best_latency = float("inf")
        for host, port in routes:
            lat = self.probe_latency(host, port)
            logger.debug(f"[PATHFINDER] {host}:{port} RTT={lat*1000:.2f}ms")
            if lat < best_latency:
                best_latency = lat
                best_route = (host, port)
        logger.info(f"[PATHFINDER] Best route: {best_route[0]}:{best_route[1]} ({best_latency*1000:.1f}ms)")
        return best_route
