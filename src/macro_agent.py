import asyncio
import logging

import requests

logger = logging.getLogger(__name__)

USGS_API = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"


class MacroAgent:
    """Macro-environmental risk agent. Ingests USGS seismic + NOAA solar feeds."""

    def __init__(self):
        self.seismic_risk = 0.0
        self.solar_risk = 0.0

    async def fetch_seismic_risk(self) -> float:
        def _fetch():
            r = requests.get(USGS_API, timeout=5)
            quakes = r.json().get("features", [])
            return max((q["properties"]["mag"] or 0 for q in quakes), default=0)

        try:
            max_mag = await asyncio.to_thread(_fetch)
            self.seismic_risk = min(1.0, max_mag / 9.0)
        except Exception as e:
            logger.error(f"[MACRO] Seismic fetch failed: {e}")
        return self.seismic_risk

    def composite_risk_multiplier(self) -> float:
        """Returns 0.0 (no risk) to 1.0 (extreme risk). Use to scale position sizing down."""
        return max(self.seismic_risk, self.solar_risk)
