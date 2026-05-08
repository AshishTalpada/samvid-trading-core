import logging

logger = logging.getLogger(__name__)

class SeismicGuard:
    """Detects micro-quakes near oil/gas infrastructure and adjusts commodity exposure."""
    def __init__(self, risk_radius_km: float = 50.0):
        self.risk_radius_km = risk_radius_km

    def assess_risk(self, epicenter_km: float, magnitude: float) -> float:
        if epicenter_km > self.risk_radius_km:
            return 0.0
        proximity_factor = 1.0 - (epicenter_km / self.risk_radius_km)
        return float(min(1.0, proximity_factor * magnitude / 5.0))
