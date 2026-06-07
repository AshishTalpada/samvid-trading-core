#!/usr/bin/env python3
"""Single-command roadmap gate: aggregate every evidence artifact and emit one verdict.

This is the capstone of the paper-to-production roadmap. It runs the offline-safe
preflight checks, regenerates the cheap deterministic evidence artifacts it can
(reliability probe, execution-audit evidence, cost-aware paper performance), loads
the artifacts that require a live/soak session (regime replay, restart soak), and
then evaluates the fail-closed promotion gate.

It never raises on missing evidence: a missing or unreadable artifact simply leaves
the corresponding gate blocked, so the only way to reach an APPROVED verdict is to
have produced genuine, complete evidence.

Usage:
    python scripts/roadmap_gate.py
    python scripts/roadmap_gate.py --db data/trading.db --artifacts-dir data
    python scripts/roadmap_gate.py --json-out data/roadmap_gate_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _path in (ROOT, SRC, SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def _safe(step: str, fn) -> tuple[Any, str | None]:
    """Run an evidence step, returning (result, error_message)."""
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 - evidence steps must never crash the gate
        return None, f"{step}: {type(exc).__name__}: {exc}"


def _load_artifact(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"artifact missing: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001
        return {}, f"artifact unreadable ({path}): {type(exc).__name__}: {exc}"


def _run_preflight() -> dict[str, Any]:
    from preflight import run_preflight

    results = run_preflight()
    checks = [
        {"name": r.name, "ok": bool(r.ok), "critical": bool(r.critical), "detail": r.detail}
        for r in results
    ]
    critical_failures = [c for c in checks if c["critical"] and not c["ok"]]
    return {"passed": not critical_failures, "checks": checks}


def _run_reliability_probe() -> dict[str, Any]:
    from backend_reliability_probe import run_backend_reliability_probe

    report = asyncio.run(run_backend_reliability_probe())
    return report.to_dict()


def _build_execution_evidence(audit_log: Path) -> dict[str, Any]:
    if not audit_log.exists():
        return {}
    from execution_evidence import build_execution_evidence

    return build_execution_evidence(str(audit_log))


def _build_paper_performance(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        return {}
    from paper_performance import build_paper_performance

    return build_paper_performance(str(db_path))


def build_roadmap_gate_report(
    *,
    db_path: Path,
    artifacts_dir: Path,
    audit_log: Path | None = None,
    soak_summary_path: Path | None = None,
) -> dict[str, Any]:
    """Assemble all evidence and evaluate the fail-closed promotion gate."""
    from promotion_readiness import evaluate_promotion_readiness

    audit_log = audit_log or (ROOT / "data" / "execution_audit.jsonl")
    soak_summary_path = soak_summary_path or (artifacts_dir / "restart_soak_summary.json")

    errors: list[str] = []

    preflight, err = _safe("preflight", _run_preflight)
    if err:
        errors.append(err)
        preflight = {"passed": False, "checks": [], "error": err}

    reliability_probe, err = _safe("reliability_probe", _run_reliability_probe)
    if err:
        errors.append(err)
        reliability_probe = {"passed": False, "error": err}

    execution_evidence, err = _safe(
        "execution_evidence", lambda: _build_execution_evidence(audit_log)
    )
    if err:
        errors.append(err)
        execution_evidence = {}

    paper_performance, err = _safe(
        "paper_performance", lambda: _build_paper_performance(db_path)
    )
    if err:
        errors.append(err)
        paper_performance = {}

    regime_replay, err = _load_artifact(artifacts_dir / "regime_replay_report.json")
    if err:
        errors.append(err)
    soak_summary, err = _load_artifact(soak_summary_path)
    if err:
        errors.append(err)

    gate = evaluate_promotion_readiness(
        execution_evidence=execution_evidence,
        reliability_probe=reliability_probe,
        regime_replay=regime_replay,
        soak_summary=soak_summary,
        paper_performance=paper_performance,
    )

    approved = bool(preflight.get("passed")) and bool(gate.get("approved"))
    blockers = list(gate.get("blockers", []))
    if not preflight.get("passed"):
        blockers.insert(0, "preflight safety checks did not pass")

    return {
        "approved": approved,
        "phases": {
            "phase_0_preflight": preflight,
            "reliability_probe": {"passed": reliability_probe.get("passed") is True},
            "phase_2_paper_performance": paper_performance.get("metrics", {}),
            "phase_3_promotion_gate": gate,
        },
        "blockers": blockers,
        "evidence_errors": errors,
    }


def _print_report(report: dict[str, Any]) -> None:
    print("=" * 70)
    print("  SOVEREIGN ROADMAP GATE - paper-to-production readiness")
    print("=" * 70)
    preflight = report["phases"]["phase_0_preflight"]
    print(f"[{'OK' if preflight.get('passed') else 'BLOCKED'}] Phase 0 - preflight safety")
    for check in preflight.get("checks", []):
        label = "OK" if check["ok"] else ("FAIL" if check["critical"] else "WARN")
        print(f"        [{label}] {check['name']}: {check['detail']}")
    rel = report["phases"]["reliability_probe"]
    print(f"[{'OK' if rel.get('passed') else 'BLOCKED'}] Reliability probe")
    metrics = report["phases"]["phase_2_paper_performance"]
    if metrics:
        print(
            f"[INFO] Phase 2 - paper performance: trades={metrics.get('trades', 0)} "
            f"expectancy_net={metrics.get('expectancy_net', 0.0):+.4f} "
            f"profit_factor={metrics.get('profit_factor', 0.0)} "
            f"max_dd={metrics.get('max_drawdown_pct', 0.0):.2%}"
        )
    else:
        print("[BLOCKED] Phase 2 - paper performance: no closed paper-trade evidence")
    gate = report["phases"]["phase_3_promotion_gate"]
    print(f"[{'OK' if gate.get('approved') else 'BLOCKED'}] Phase 3 - promotion gate")
    if report["blockers"]:
        print("\n  Blockers:")
        for blocker in report["blockers"]:
            print(f"    - {blocker}")
    if report["evidence_errors"]:
        print("\n  Missing/unreadable evidence (fail-closed):")
        for err in report["evidence_errors"]:
            print(f"    - {err}")
    print("=" * 70)
    print(f"  VERDICT: {'APPROVED FOR PROMOTION' if report['approved'] else 'NOT APPROVED'}")
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the end-to-end roadmap promotion gate.")
    parser.add_argument("--db", default=str(ROOT / "data" / "trading.db"))
    parser.add_argument("--artifacts-dir", default=str(ROOT / "data"))
    parser.add_argument("--audit-log", default=str(ROOT / "data" / "execution_audit.jsonl"))
    parser.add_argument("--soak-summary", default=None)
    parser.add_argument("--json-out", default=str(ROOT / "data" / "roadmap_gate_report.json"))
    args = parser.parse_args(argv)

    report = build_roadmap_gate_report(
        db_path=Path(args.db),
        artifacts_dir=Path(args.artifacts_dir),
        audit_log=Path(args.audit_log),
        soak_summary_path=Path(args.soak_summary) if args.soak_summary else None,
    )

    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _print_report(report)
    return 0 if report["approved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
