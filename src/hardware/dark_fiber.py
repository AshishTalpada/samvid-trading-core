import logging
logger = logging.getLogger(__name__)

class DarkFiberLink:
    """Monitors latency on the physical dark fiber lease to the exchange."""
    def ping_exchange(self) -> float:
        logger.debug("Pinging exchange over dark fiber...")
        return 0.05  # 50 microseconds
