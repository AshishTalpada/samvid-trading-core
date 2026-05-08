import logging
logger = logging.getLogger(__name__)

class SSDWearMonitor:
    """Monitors NVMe TBW (Terabytes Written) to prevent sudden drive failure."""
    def __init__(self, max_tbw: int = 1200):
        self.max_tbw = max_tbw

    def check_wear(self, current_tbw: int) -> bool:
        if current_tbw > self.max_tbw * 0.9:
            logger.critical(f"SSD Wear Critical: {current_tbw} TBW. Replace drive immediately.")
            return False
        return True
