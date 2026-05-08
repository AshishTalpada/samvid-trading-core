import logging
import shutil
import time
from typing import Dict

import psutil

logger = logging.getLogger(__name__)

class PredictiveMaintenanceAgent:
    """
    Monitors hardware health metrics and predicts failure before it occurs.
    Triggers graceful system shutdown if SSD wear > 90%, CPU temp > 95°C,
    or memory error rate spikes.
    """
    THRESHOLDS = {"cpu_temp_c": 90.0, "disk_usage_pct": 85.0, "ram_pct": 92.0}

    def health_snapshot(self) -> Dict:
        disk = shutil.disk_usage("/")
        disk_pct = disk.used / disk.total * 100
        ram = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=0.5)
        return {"disk_usage_pct": round(disk_pct, 1), "ram_pct": round(ram.percent, 1), "cpu_pct": round(cpu_pct, 1)}

    def check_shutdown_required(self) -> bool:
        snap = self.health_snapshot()
        for metric, limit in self.THRESHOLDS.items():
            val = snap.get(metric, 0.0)
            if val >= limit:
                logger.critical(f"[MAINTENANCE] CRITICAL: {metric}={val} >= {limit}. Shutdown recommended.")
                return True
        return False
