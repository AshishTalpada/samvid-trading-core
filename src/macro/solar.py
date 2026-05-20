import asyncio
import logging

import requests

logger = logging.getLogger(__name__)

NOAA_SOLAR_API = "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json"


class SolarActivityMonitor:
    """
    Monitors solar geomagnetic activity (Kp-index) from NOAA SWPC.
    High Kp-index (>6) disrupts satellite communications, GPS timing, and
    shortwave radio — all used by HFT firms for nanosecond arbitrage.
    Sovereign reduces satellite-dependent data weight during solar storms.
    """

    async def fetch_kp_index(self) -> float:
        def _fetch():
            r = requests.get(NOAA_SOLAR_API, timeout=5)
            data = r.json()
            latest = data[-1] if data else {}
            kp = float(latest.get("kp_index", 0.0))
            logger.info(f"[SOLAR] Current Kp-index: {kp}")
            return kp

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error(f"[SOLAR] NOAA fetch failed: {e}")
            return 0.0

    def satellite_data_weight(self, kp: float) -> float:
        if kp >= 7.0:
            return 0.0
        if kp >= 5.0:
            return 0.5
        if kp >= 3.0:
            return 0.8
        return 1.0

