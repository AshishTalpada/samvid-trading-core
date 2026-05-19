import logging

logger = logging.getLogger(__name__)

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class ThermalAwarenessEngine:
    """
    Monitors CPU and GPU thermal state to dynamically scale intelligence depth.
    If GPU temp > 85°C, disables non-critical AI reasoning layers.
    If CPU temp > 90°C, reduces quorum agent count to prevent thermal shutdown.
    """

    def get_temps(self) -> dict:
        if not HAS_PSUTIL:
            return {}
        try:
            raw = psutil.sensors_temperatures()
            return {k: max(t.current for t in v) for k, v in raw.items()}
        except Exception:
            return {}

    def intelligence_depth_multiplier(self) -> float:
        temps = self.get_temps()
        max_temp = max(temps.values(), default=50.0)
        if max_temp >= 90.0:
            logger.critical(f"[THERMAL] {max_temp:.1f}°C — reducing intelligence to 20%!")
            return 0.2
        if max_temp >= 80.0:
            logger.warning(f"[THERMAL] {max_temp:.1f}°C — reducing intelligence to 60%")
            return 0.6
        return 1.0

    def should_throttle_agents(self) -> bool:
        return self.intelligence_depth_multiplier() < 1.0
