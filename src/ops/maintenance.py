from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class PredictiveMaintenanceAgent:
    """Monitor host resource pressure with confirmed, non-destructive alerts."""

    THRESHOLDS = {
        "cpu_temp_c": 90.0,
        "cpu_pct": 98.0,
        "disk_usage_pct": 90.0,
        "ram_pct": 92.0,
    }

    def __init__(self, root_path: str | Path = ".", confirmation_samples: int = 3) -> None:
        self.root_path = Path(root_path).resolve()
        self.confirmation_samples = max(1, int(confirmation_samples))
        self._consecutive_breaches: dict[str, int] = {}

    @staticmethod
    def _max_cpu_temperature() -> float | None:
        try:
            sensors = psutil.sensors_temperatures(fahrenheit=False)
        except (AttributeError, OSError):
            return None
        readings = [
            float(entry.current)
            for entries in sensors.values()
            for entry in entries
            if entry.current is not None and float(entry.current) > 0.0
        ]
        return max(readings) if readings else None

    def health_snapshot(self) -> dict[str, float]:
        disk = shutil.disk_usage(self.root_path)
        ram = psutil.virtual_memory()
        snapshot = {
            "disk_usage_pct": round(disk.used / disk.total * 100.0, 1),
            "ram_pct": round(float(ram.percent), 1),
            "cpu_pct": round(float(psutil.cpu_percent(interval=None)), 1),
        }
        cpu_temp = self._max_cpu_temperature()
        if cpu_temp is not None:
            snapshot["cpu_temp_c"] = round(cpu_temp, 1)
        return snapshot

    def evaluate(self) -> dict[str, Any]:
        snapshot = self.health_snapshot()
        breached: list[str] = []
        confirmed: list[str] = []
        for metric, limit in self.THRESHOLDS.items():
            value = snapshot.get(metric)
            if value is not None and value >= limit:
                breached.append(metric)
                count = self._consecutive_breaches.get(metric, 0) + 1
                self._consecutive_breaches[metric] = count
                if count >= self.confirmation_samples:
                    confirmed.append(metric)
            else:
                self._consecutive_breaches[metric] = 0

        if confirmed:
            status = "CRITICAL"
            detail = ", ".join(
                f"{metric}={snapshot[metric]:.1f}>={self.THRESHOLDS[metric]:.1f}"
                for metric in confirmed
            )
            logger.critical("Host resource pressure confirmed: %s", detail)
        elif breached:
            status = "DEGRADED"
            detail = "awaiting confirmation: " + ", ".join(breached)
            logger.warning("Host resource pressure detected: %s", detail)
        else:
            status = "ONLINE"
            detail = (
                f"cpu={snapshot['cpu_pct']:.1f}%, ram={snapshot['ram_pct']:.1f}%, "
                f"disk={snapshot['disk_usage_pct']:.1f}%"
            )

        return {
            "status": status,
            "detail": detail,
            "snapshot": snapshot,
            "breached": breached,
            "confirmed": confirmed,
        }

    def check_shutdown_required(self) -> bool:
        """Return a recommendation only; this method never terminates the process."""
        return self.evaluate()["status"] == "CRITICAL"
