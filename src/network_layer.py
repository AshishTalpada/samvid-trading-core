import logging
import socket
import time
from typing import Optional

logger = logging.getLogger(__name__)

class FiberFailoverLayer:
    """
    Dual-fiber optical failover network layer.
    Monitors primary and secondary fiber paths via TCP probe and switches
    automatically to the lower-latency or available path.
    """
    def __init__(self, primary: tuple[str,int], secondary: tuple[str,int], probe_interval: float = 0.5):
        self.primary = primary
        self.secondary = secondary
        self.active = primary
        self.probe_interval = probe_interval

    def _probe_latency(self, host: str, port: int, timeout: float = 0.2) -> Optional[float]:
        try:
            t0 = time.perf_counter()
            s = socket.create_connection((host, port), timeout=timeout)
            s.close()
            return time.perf_counter() - t0
        except OSError:
            return None

    def select_path(self) -> tuple[str, int]:
        p_lat = self._probe_latency(*self.primary)
        s_lat = self._probe_latency(*self.secondary)
        if p_lat is None and s_lat is None:
            logger.critical("[FIBER] Both paths unreachable!")
            return self.active
        if p_lat is None:
            logger.warning("[FIBER] Primary down. Switching to secondary.")
            self.active = self.secondary
        elif s_lat is None or p_lat <= s_lat:
            self.active = self.primary
        else:
            self.active = self.secondary
        return self.active
