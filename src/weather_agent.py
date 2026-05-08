import logging

logger = logging.getLogger(__name__)

class WeatherAgent:
    """Correlates weather anomalies with consumer retail and commodity performance."""
    IMPACT_MAP = {
        "blizzard": {"retail": -0.15, "energy": 0.20},
        "drought":  {"agriculture": -0.25, "water_utilities": 0.10},
        "hurricane": {"construction": 0.10, "insurance": -0.20},
    }

    def get_sector_impact(self, weather_event: str) -> dict[str, float]:
        impact = self.IMPACT_MAP.get(weather_event.lower(), {})
        if impact:
            logger.info(f"Weather event '{weather_event}' sector impact: {impact}")
        return impact
