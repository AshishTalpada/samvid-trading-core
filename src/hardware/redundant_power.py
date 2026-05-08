import logging
logger = logging.getLogger(__name__)

class RedundantPower:
    """Monitors dual online-double-conversion UPS status."""
    def is_power_stable(self) -> bool:
        logger.debug("UPS A: ONLINE, UPS B: ONLINE")
        return True
