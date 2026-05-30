"""Generate a paper-to-production readiness report from evidence artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promotion_readiness import evaluate_promotion_readiness  # noqa: E402


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execution-evidence", default="data/execution_audit_report.json")
    parser.add_argument("--reliability-probe", default="data/backend_reliability_probe.json")
    parser.add_argument("--regime-replay", default="data/regime_replay_report.json")
    parser.add_argument("--paper-performance", default="data/paper_performance_report.json")
    parser.add_argument("--soak-summary", required=True)
    parser.add_argument("--json-out", default="data/promotion_readiness_report.json")
    args = parser.parse_args()

    report = evaluate_promotion_readiness(
        execution_evidence=_load(args.execution_evidence),
        reliability_probe=_load(args.reliability_probe),
        regime_replay=_load(args.regime_replay),
        soak_summary=_load(args.soak_summary),
        paper_performance=_load(args.paper_performance),
    )
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["approved"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
