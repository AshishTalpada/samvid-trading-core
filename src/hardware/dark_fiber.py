import logging
import socket
import time

logger = logging.getLogger(__name__)


class DarkFiberLatencyMonitor:
    """
    Monitors leased dark fiber links via TCP RTT probing.
    Dark fiber = raw optical fiber leased directly, no ISP overhead.
    Achieves ~1μs latency between co-located data centres.
    Alerts if link degrades beyond 50μs threshold.
    """

    ALERT_THRESHOLD_US = 50.0

    def __init__(self, endpoints: list[tuple[str, int]] | None = None):
        self.endpoints = endpoints or [("127.0.0.1", 4001)]
        self._latency_history: dict[str, list[float]] = {}

    def probe_link(self, host: str, port: int, samples: int = 5) -> float:
        latencies = []
        for _ in range(samples):
            try:
                t0 = time.perf_counter()
                s = socket.create_connection((host, port), timeout=0.01)
                s.close()
                latencies.append((time.perf_counter() - t0) * 1e6)
            except OSError:
                latencies.append(9999.0)
        return min(latencies) if latencies else 9999.0

    def check_all(self) -> dict[str, float]:
        results: dict[str, float] = {}
        for host, port in self.endpoints:
            key = f"{host}:{port}"
            lat = self.probe_link(host, port)
            results[key] = lat
            if key not in self._latency_history:
                self._latency_history[key] = []
            self._latency_history[key].append(lat)
            if lat > self.ALERT_THRESHOLD_US:
                logger.warning(
                    f"[DARK FIBER] Link {key} degraded: {lat:.1f}μs > {self.ALERT_THRESHOLD_US}μs"
                )
        return results
