"""The roadmap gate must be fail-closed: missing evidence can never yield approval."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "scripts", ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def test_roadmap_gate_is_fail_closed_without_evidence(tmp_path):
    from roadmap_gate import build_roadmap_gate_report

    report = build_roadmap_gate_report(
        db_path=tmp_path / "trading.db",
        artifacts_dir=tmp_path,
        audit_log=tmp_path / "execution_audit.jsonl",
        soak_summary_path=tmp_path / "restart_soak_summary.json",
    )

    assert report["approved"] is False
    assert "phase_0_preflight" in report["phases"]
    assert "phase_3_promotion_gate" in report["phases"]
    assert isinstance(report["blockers"], list)
    assert report["blockers"], "missing evidence must produce explicit blockers"
    # Missing regime-replay and soak artifacts must be reported as fail-closed evidence gaps.
    assert any("restart_soak_summary.json" in err for err in report["evidence_errors"])
