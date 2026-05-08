import logging
logger = logging.getLogger(__name__)

class TectonicSensor:
    """Monitors seismic strain data near key refineries and commodity infrastructure."""
    def __init__(self, alert_threshold: float = 3.5):
        self.alert_threshold = alert_threshold

    def evaluate(self, magnitude: float, location: str) -> bool:
        if magnitude >= self.alert_threshold:
            logger.warning(f"Seismic event near {location}: M{magnitude:.1f}. Raising commodity risk.")
            return True
        return False
