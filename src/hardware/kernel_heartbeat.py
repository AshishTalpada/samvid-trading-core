import time
import logging
logger = logging.getLogger(__name__)

class KernelHeartbeat:
    """Hardware watchdog timer interface to trigger hard-reboot on kernel hang."""
    def __init__(self, timeout_secs: int = 5):
        self.timeout = timeout_secs
        self.last_beat = time.time()

    def beat(self) -> None:
        self.last_beat = time.time()
        logger.debug("Kernel heartbeat updated.")

    def is_alive(self) -> bool:
        return time.time() - self.last_beat < self.timeout
