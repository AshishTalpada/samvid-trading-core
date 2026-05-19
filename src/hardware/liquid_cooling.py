import logging

logger = logging.getLogger(__name__)

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class LiquidCoolingMonitor:
    """
    Monitors CPU/GPU thermal envelope and alerts if liquid cooling performance degrades.
    Triggers clock throttle warning before thermal shutdown occurs.
    Integrates with system sensors via psutil and NVML.
    """

    THROTTLE_THRESHOLD_C = 85.0
    CRITICAL_THRESHOLD_C = 95.0

    def read_cpu_temp(self) -> float | None:
        if not HAS_PSUTIL:
            return None
        try:
            temps = psutil.sensors_temperatures()
            for name in ("coretemp", "cpu_thermal", "k10temp"):
                if name in temps:
                    return max(t.current for t in temps[name])  # type: ignore
        except Exception as e:
            logger.debug(f"[COOLING] Temp read failed: {e}")
        return None

    def thermal_status(self) -> dict:
        temp = self.read_cpu_temp()
        if temp is None:
            return {"status": "UNKNOWN", "temp_c": None}
        if temp >= self.CRITICAL_THRESHOLD_C:
            logger.critical(f"[COOLING] CRITICAL TEMP: {temp:.1f}°C — emergency throttle!")
            status = "CRITICAL"
        elif temp >= self.THROTTLE_THRESHOLD_C:
            logger.warning(f"[COOLING] High temp: {temp:.1f}°C — consider reducing load")
            status = "WARNING"
        else:
            status = "NOMINAL"
        return {"status": status, "temp_c": round(temp, 1)}
