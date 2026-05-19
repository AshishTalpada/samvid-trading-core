import logging
import time
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)


class VIXCircuitBreaker:
    """
    Global macro safety valve. Kills all positions if VIX spikes brutally.
    Maintains a rolling 5-minute window of VIX ticks to calculate percentage change.
    """

    def __init__(self, spike_threshold: float = 0.20, window_seconds: int = 300):
        self.spike_threshold = spike_threshold
        self.window_seconds = window_seconds
        self.tick_history: Any = deque()  # tuples of (timestamp, vix_value)

    def process_vix_tick(self, vix_value: float) -> bool:
        """
        Ingests a VIX value. Returns True if a catastrophic spike is
        detected, triggering liquidation.
        """
        current_time = time.time()
        self.tick_history.append((current_time, vix_value))

        # Evict old ticks
        while self.tick_history and current_time - self.tick_history[0][0] > self.window_seconds:
            self.tick_history.popleft()

        if len(self.tick_history) < 2:
            return False

        oldest_vix = self.tick_history[0][1]
        percent_change = (vix_value - oldest_vix) / oldest_vix

        if percent_change >= self.spike_threshold:
            logger.critical(
                f"VIX FLASH SPIKE DETECTED! {percent_change * 100:.2f}% in < {self.window_seconds}s"
            )
            return True

        return False
