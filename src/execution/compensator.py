import asyncio
import logging
import time

logger = logging.getLogger(__name__)

class LatencyCompensator:
    """
    Predictive order pre-submission compensator.
    Measures round-trip latency to the broker and submits orders N ms early
    so they arrive at the exchange at the exact intended time.
    """
    def __init__(self, broker_host: str = "localhost", broker_port: int = 4001):
        self.host = broker_host
        self.port = broker_port
        self._rtt_ms: float = 5.0
        self._history: list[float] = []

    def measure_rtt(self) -> float:
        import socket
        try:
            t0 = time.perf_counter()
            s = socket.create_connection((self.host, self.port), timeout=0.5)
            s.close()
            rtt = (time.perf_counter() - t0) * 1000
            self._history.append(rtt)
            if len(self._history) > 20: self._history.pop(0)
            self._rtt_ms = sum(self._history) / len(self._history)
            return self._rtt_ms
        except OSError:
            return self._rtt_ms

    def pre_submission_delay_ms(self, target_time_ms: float) -> float:
        now_ms = time.time() * 1000
        lead_time = target_time_ms - now_ms - self._rtt_ms
        return max(0.0, lead_time)

    async def submit_at(self, target_time_ms: float, callback) -> None:
        delay_ms = self.pre_submission_delay_ms(target_time_ms)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        logger.info(f"[COMPENSATOR] Submitting order (RTT={self._rtt_ms:.2f}ms pre-lead)")
        await callback()
