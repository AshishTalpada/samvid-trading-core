import logging
from typing import Dict

import requests

logger = logging.getLogger(__name__)

class WeatherCorrelationAgent:
    """
    Correlates weather anomalies with retail, energy, and agricultural sectors.
    Cold snaps -> NatGas spike. Drought -> Crop futures bull. Heavy rain -> Retail miss.
    Uses OpenWeatherMap or NOAA Climate API.
    """
    NOAA_BASE = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
    SECTOR_MAP = {
        "cold_snap": ["UNG", "CHK", "EQT"],
        "drought": ["ZW", "ZC", "ZS", "MOS"],
        "hurricane": ["RIG", "HAL", "SLB", "HES"],
        "heat_wave": ["SO", "EXC", "DUK"],
    }

    def classify_anomaly(self, temp_deviation_c: float, precip_deviation_mm: float) -> str:
        if temp_deviation_c < -5: return "cold_snap"
        if temp_deviation_c > 5 and precip_deviation_mm < -20: return "drought"
        if temp_deviation_c > 5: return "heat_wave"
        return "normal"

    def get_affected_tickers(self, anomaly: str) -> list[str]:
        return self.SECTOR_MAP.get(anomaly, [])

    def weather_alpha(self, temp_dev: float, precip_dev: float) -> Dict:
        anomaly = self.classify_anomaly(temp_dev, precip_dev)
        tickers = self.get_affected_tickers(anomaly)
        logger.info(f"[WEATHER] Anomaly={anomaly} | Affected: {tickers}")
        return {"anomaly": anomaly, "tickers": tickers, "impact": "BULLISH" if tickers else "NONE"}
