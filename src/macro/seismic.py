import logging
import math
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

class SeismicInfrastructureMonitor:
    """
    Infra Safety: Detects micro-quakes near critical global supply chain infrastructure.
    Pulls real-time GeoJSON data from the USGS and calculates the seismic stress
    applied to strategic locations (e.g., Cushing OK oil storage, TSMC Fab facilities in Taiwan).
    """

    USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

    # Critical targets mapping: Name -> (Latitude, Longitude)
    CRITICAL_TARGETS = {
        "Cushing_Oil_Hub": (35.9822, -96.7675),
        "TSMC_Fab_18_Taiwan": (23.1118, 120.2783),
        "Strait_of_Hormuz": (26.5667, 56.2500),
        "Panama_Canal": (9.1011, -79.6953)
    }

    def __init__(self, alert_threshold_richter: float = 4.0):
        self.threshold = alert_threshold_richter

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance in kilometers between two points."""
        R = 6371.0 # Earth radius in km
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def fetch_recent_quakes(self) -> List[Dict]:
        try:
            response = requests.get(self.USGS_URL, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data.get("features", [])
        except Exception as e:
            logger.error(f"Failed to fetch USGS Seismic data: {e}")
            return []

    def scan_for_disruptions(self) -> list[dict]:
        """
        Scans recent earthquakes and calculates the disruption risk to global infrastructure.
        Returns a list of alerts.
        """
        quakes = self.fetch_recent_quakes()
        alerts = []

        for quake in quakes:
            props = quake["properties"]
            geom = quake["geometry"]

            mag = props.get("mag")
            if not mag or mag < self.threshold:
                continue

            # USGS coords: [longitude, latitude, depth]
            lon, lat, depth = geom["coordinates"]
            place = props.get("place", "Unknown Location")

            for target_name, (t_lat, t_lon) in self.CRITICAL_TARGETS.items():
                distance_km = self.haversine_distance(lat, lon, t_lat, t_lon)

                # If a magnitude 4+ quake happens within 100km of a critical target, flag it.
                # If a magnitude 6+ happens within 300km, flag it.
                if (mag >= 4.0 and distance_km < 100) or (mag >= 6.0 and distance_km < 300):
                    alert = {
                        "target": target_name,
                        "distance_km": distance_km,
                        "magnitude": mag,
                        "location": place,
                        "depth_km": depth
                    }
                    logger.critical(f"SEISMIC THREAT: Magnitude {mag:.1f} quake detected {distance_km:.0f}km from {target_name} ({place}).")
                    alerts.append(alert)

        return alerts
