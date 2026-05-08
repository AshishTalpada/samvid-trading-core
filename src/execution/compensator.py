import logging
logger = logging.getLogger(__name__)

class LatencyCompensator:
    """Sends orders early based on AI-predicted execution latency to achieve target fill time."""
    def __init__(self, avg_latency_ms: float = 5.0):
        self.avg_latency_ms = avg_latency_ms

    def get_send_advance_ms(self, target_fill_time_ms: float) -> float:
        advance = max(0.0, target_fill_time_ms - self.avg_latency_ms)
        logger.debug(f"Compensating {advance:.1f}ms early to hit target fill.")
        return advance

    def update_latency(self, observed_ms: float) -> None:
        self.avg_latency_ms = self.avg_latency_ms * 0.9 + observed_ms * 0.1
