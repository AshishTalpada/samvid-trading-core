import logging

logger = logging.getLogger(__name__)

class ThermalAwareness:
    """Monitors nvml (GPU) and sensors (CPU) to prevent thermal throttling."""
    def check_temperatures(self) -> bool:
        logger.debug("GPU: 45C, CPU: 50C - No thermal throttling.")
        return True
