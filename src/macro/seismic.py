import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
CRITICAL_REGIONS = {
    "oil":    [(29.7, -95.4, "Houston TX"),    (36.2, 49.6,  "Khuzestan Iran")],
    "chips":  [(24.9, 121.6, "Taiwan TSMC"),   (37.3, 127.0, "Samsung Korea")],
    "ports":  [(33.7, -118.2,"LA/LB Port"),    (22.3, 114.2, "Hong Kong")],
}


class SeismicRiskMonitor:
    """
    Monitors USGS real-time earthquake data near critical commodity infrastructure.
    A magnitude 6.5+ quake near an oil refinery or semiconductor fab
    should immediately trigger a reduction in related equity/commodity exposure.
    """

    def fetch_recent(self, min_mag: float = 5.0, limit: int = 50) -> List[Dict]:
        try:
            r = requests.get(USGS_API, params={"format": "geojson", "minmagnitude": min_mag, "limit": limit}, timeout=6)
            return [{"mag": f["properties"]["mag"], "lat": f["geometry"]["coordinates"][1],
                     "lon": f["geometry"]["coordinates"][0], "place": f["properties"]["place"]}
                    for f in r.json().get("features", [])]
        except Exception as e:
            logger.error(f"[SEISMIC] USGS fetch failed: {e}")
            return []

    def risk_near_region(self, quakes: List[Dict], region_type: str, radius_deg: float = 2.0) -> float:
        sites = CRITICAL_REGIONS.get(region_type, [])
        max_risk = 0.0
        for quake in quakes:
            for lat, lon, name in sites:
                dist = ((quake["lat"] - lat)**2 + (quake["lon"] - lon)**2)**0.5
                if dist <= radius_deg:
                    risk = min(1.0, (quake["mag"] - 4.0) / 5.0)
                    if risk > max_risk:
                        max_risk = risk
                        logger.warning(f"[SEISMIC] M{quake['mag']} near {name} -> risk={risk:.2f}")
        return round(max_risk, 3)
