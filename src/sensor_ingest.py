import logging
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class SensorIngestAgent:
    """
    Ingests multi-source physical sensor data for alternative signal generation.
    Sources: USGS seismic, NOAA weather, AIS ship tracking, IoT industrial sensors.
    Produces a unified sensor risk score for position sizing adjustment.
    """

    def fetch_usgs_events(self, min_magnitude: float = 5.0) -> List[Dict]:
        try:
            url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude={min_magnitude}&limit=20"
            r = requests.get(url, timeout=6)
            features = r.json().get("features", [])
            return [
                {
                    "mag": f["properties"]["mag"],
                    "place": f["properties"]["place"],
                    "time": f["properties"]["time"],
                }
                for f in features
            ]
        except Exception as e:
            logger.error(f"[SENSOR] USGS fetch failed: {e}")
            return []

    def compute_risk_score(self, seismic_events: List[Dict], solar_kp: float) -> float:
        seismic_risk = min(1.0, sum(e.get("mag", 0) for e in seismic_events) / 50.0)
        solar_risk = min(1.0, solar_kp / 9.0)
        composite = seismic_risk * 0.6 + solar_risk * 0.4
        logger.info(
            f"[SENSOR] Composite risk={composite:.3f} (seismic={seismic_risk:.2f}, solar={solar_risk:.2f})"
        )
        return round(composite, 3)  # type: ignore
