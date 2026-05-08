import logging
import time

logger = logging.getLogger(__name__)

class WatchdogPulse:
    """Tracks user presence and adjusts risk exposure if user is away."""
    def __init__(self, idle_timeout_secs: int = 300):
        self.timeout = idle_timeout_secs
        self.last_heartbeat = time.time()

    def pulse(self) -> None:
        self.last_heartbeat = time.time()

    def is_user_away(self) -> bool:
        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.timeout:
            logger.warning(f"User away for {elapsed:.0f}s. Applying conservative risk.")
            return True
        return False
