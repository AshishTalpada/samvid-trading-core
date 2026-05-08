import logging

logger = logging.getLogger(__name__)

class SolarFlareGuard:
    """Reduces satellite-dependent data risk during geomagnetic storm events."""
    KP_RISK_THRESHOLD = 5

    def should_reduce_satellite_exposure(self, kp_index: float) -> bool:
        if kp_index >= self.KP_RISK_THRESHOLD:
            logger.warning(f"Solar storm: Kp={kp_index}. Reducing satellite data reliance.")
            return True
        return False
