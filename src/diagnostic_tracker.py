import ast
import hashlib
import logging
import os
from dataclasses import dataclass

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
    SETO V7.0 Diagnostic Tracking System.
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
        """
        Runs multiple diagnostic engines (AST, Linters, etc.)
        Inspired by getDiagnostics in Claude-Code.
        """
        diagnostics = []
        if not os.path.exists(file_path):
            return []

        # 1. AST Syntax Check (The 'Blood' check)
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            diagnostics.append(
                Diagnostic(
                    message=str(e),
                    severity="Error",
                    line=e.lineno,
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

        # 2. Logic Audit (Regex for common SETO anti-patterns)
        # e.g., UnboundLocalError potentials, naked exceptions
        if "except:" in content:
            diagnostics.append(
                Diagnostic(
                    message="Naked 'except:' detected. High risk of silent failure.",
                    severity="Warning",
                    line=0,  # Simplified for now
                    character=0,
                    source="SETO_AUDIT",
                )
            )

        return diagnostics

    def _get_file_hash(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()  # nosec B324

    def format_summary(self, diagnostics: list[Diagnostic]) -> str:
        if not diagnostics:
            return "No issues detected."

        summary = []
        for d in diagnostics:
            sym = "✖" if d.severity == "Error" else "⚠"
            summary.append(f"  {sym} [Line {d.line}] {d.message} ({d.source})")
        return "\n".join(summary)
