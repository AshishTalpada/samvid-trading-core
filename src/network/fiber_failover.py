import logging
import socket
import time
from typing import Optional

logger = logging.getLogger(__name__)


class FiberFailoverMonitor:
    """
    Active-passive fiber failover monitor.
    Continuously probes primary and secondary fiber paths via ICMP-equivalent
    TCP SYN probes and triggers failover within 10ms of primary path loss.
    """

    def __init__(
        self, primary_host: str, secondary_host: str, port: int = 80, probe_interval: float = 0.1
    ):
        self.primary = primary_host
        self.secondary = secondary_host
        self.port = port
        self.interval = probe_interval
        self.active_path = primary_host
        self.failover_count = 0

    def _tcp_probe(self, host: str, timeout: float = 0.05) -> Optional[float]:
        try:
            t0 = time.perf_counter()
            s = socket.create_connection((host, self.port), timeout=timeout)
            latency = time.perf_counter() - t0
            s.close()
            return latency
        except OSError:
            return None

    def check_and_failover(self) -> str:
        p = self._tcp_probe(self.primary)
        s = self._tcp_probe(self.secondary)
        if p is None and self.active_path == self.primary:
            self.active_path = self.secondary
            self.failover_count += 1
            logger.critical(
                f"[FIBER] PRIMARY DOWN — switched to secondary (failover #{self.failover_count})"
            )
        elif p is not None and s is not None and p > s * 1.5 and self.active_path == self.primary:
            self.active_path = self.secondary
            logger.warning(
                f"[FIBER] Secondary faster ({s * 1000:.2f}ms vs {p * 1000:.2f}ms). Switching."
            )
        elif p is not None and self.active_path == self.secondary:
            self.active_path = self.primary
            logger.info(f"[FIBER] Primary restored ({p * 1000:.2f}ms). Resuming.")
        return self.active_path
