import ast
import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)

@dataclass
class Diagnostic:
    message: str
    severity: str  # Error, Warning, Info
    line: int
    character: int
    source: str | None = None
    code: str | None = None

    def __eq__(self, other):
        if not isinstance(other, Diagnostic):
            return False
        return (
            self.message == other.message
            and self.severity == other.severity
            and self.line == other.line
            and self.character == other.character
        )

class DiagnosticTracker:
    """
    Inspired by Claude-Code's DiagnosticTrackingService.ts.
    Maintains baselines and detects 'New Bleeding' (regressions).
    """
    def __init__(self) -> None:
        self.baselines: dict[str, list[Diagnostic]] = {}
        self.last_hashes: dict[str, str] = {}

    def capture_baseline(self, file_path: str) -> None:
        """Captures a baseline of diagnostics for a file before it is edited."""
        diagnostics = self._run_diagnostics(file_path)
        self.baselines[file_path] = diagnostics
        self.last_hashes[file_path] = self._get_file_hash(file_path)
        logger.info(
            f"DiagnosticTracker: Baseline captured for {file_path} ({len(diagnostics)} issues)."
        )

    def get_new_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Returns only the NEW diagnostics that weren't in the baseline."""
        current_diagnostics = self._run_diagnostics(file_path)
        baseline = self.baselines.get(file_path, [])
        new_issues = [d for d in current_diagnostics if d not in baseline]
        if new_issues:
            logger.warning(
                f"DiagnosticTracker: {len(new_issues)} NEW diagnostic issues detected in {file_path}!"
            )
        return new_issues

    def _run_diagnostics(self, file_path: str) -> list[Diagnostic]:
        """Runs multiple diagnostic engines (AST, Linters, etc.)."""
        diagnostics = []
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            diagnostics.append(
                Diagnostic(
                    message=str(e),
                    severity="Error",
                    line=e.lineno or 0,
                    character=e.offset or 0,
                    source="AST",
                )
            )
        except Exception as e:
            diagnostics.append(
                Diagnostic(
                    message=f"Diagnostic Engine Failure: {e}",
                    severity="Error",
                    line=0,
                    character=0,
                    source="SYSTEM",
                )
            )
        if "except:" in content:
            diagnostics.append(
                Diagnostic(
                    message="Naked 'except:' detected. High risk of silent failure.",
                    severity="Warning",
                    line=0,
                    character=0,
                    source="SETO_AUDIT",
                )
            )
        return diagnostics

    def _get_file_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def format_summary(self, diagnostics: list[Diagnostic]) -> str:
        if not diagnostics:
            return "No issues detected."
        summary = []
        for d in diagnostics:
            sym = "✖" if d.severity == "Error" else "⚠"
            summary.append(f"  {sym} [Line {d.line}] {d.message} ({d.source})")
        return "\n".join(summary)

class SovereignDiagnosticTracker:
    '''
    Hardware & Logic Diagnostic Engine.
    Exposes raw system telemetry (CPU temps, RAM consumption, ZMQ message latencies)
    into a structured format designed to be scraped by Prometheus and visualized in Grafana.
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
        self.metrics[key] = value

    def increment_metric(self, key: str):
        if key not in self.metrics:
            self.metrics[key] = 0
        self.metrics[key] += 1

    def scrape_hardware_telemetry(self) -> Dict[str, float]:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_info = self.process.memory_info()
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
        return {**self.metrics, **telemetry}

    def emit_prometheus_metrics(self) -> str:
        data = self.scrape_hardware_telemetry()
        lines = []
        for key, value in data.items():
            safe_key = f"sovereign_{key.replace('-', '_')}"
            lines.append(f"# HELP {safe_key} Sovereign internal telemetry metric")
            lines.append(f"# TYPE {safe_key} gauge")
            lines.append(f"{safe_key} {value}")
        return "\n".join(lines)
