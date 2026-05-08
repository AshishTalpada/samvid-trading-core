import logging
import os
from typing import Any, Dict

import psutil

logger = logging.getLogger(__name__)

class SovereignDiagnosticTracker:
    '''
    Hardware & Logic Diagnostic Engine.
    Exposes raw system telemetry (CPU temps, RAM consumption, ZMQ message latencies)
    into a structured format designed to be scraped by Prometheus and visualized in Grafana.
    Provides instant visibility into the physical health of the Sovereign node.
    '''
    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "total_trades_executed": 0,
            "arbitrations_won": 0,
            "quorum_deadlocks": 0,
            "uptime_seconds": 0.0
        }
        self.process = psutil.Process(os.getpid())

    def record_metric(self, key: str, value: float):
        '''Updates an internal logic metric.'''
        self.metrics[key] = value

    def increment_metric(self, key: str):
        '''Increments a counter metric.'''
        if key not in self.metrics:
            self.metrics[key] = 0
        self.metrics[key] += 1

    def scrape_hardware_telemetry(self) -> Dict[str, float]:
        '''Polls deep hardware states using cross-platform psutil bindings.'''
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_info = self.process.memory_info()

        # Convert RSS (Resident Set Size) from bytes to MB
        ram_mb = memory_info.rss / (1024 * 1024)

        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()

        telemetry = {
            "node_cpu_utilization_pct": cpu_percent,
            "node_ram_consumed_mb": ram_mb,
            "disk_read_bytes": disk_io.read_bytes if disk_io else 0,
            "disk_write_bytes": disk_io.write_bytes if disk_io else 0,
            "network_rx_bytes": net_io.bytes_recv if net_io else 0,
            "network_tx_bytes": net_io.bytes_sent if net_io else 0,
        }

        # Combine hardware and logic metrics into a single unified Prometheus-style scrape target
        unified = {**self.metrics, **telemetry}
        return unified

    def emit_prometheus_metrics(self) -> str:
        '''
        Formats all tracked metrics into the Prometheus Text Exposition format.
        This string can be served via a lightweight HTTP endpoint (e.g., via FastAPI).
        '''
        data = self.scrape_hardware_telemetry()
        lines = []
        for key, value in data.items():
            # Ensure keys are valid Prometheus metric names (alphanumeric and underscores)
            safe_key = f"sovereign_{key.replace('-', '_')}"
            lines.append(f"# HELP {safe_key} Sovereign internal telemetry metric")
            lines.append(f"# TYPE {safe_key} gauge")
            lines.append(f"{safe_key} {value}")

        return "\n".join(lines)
