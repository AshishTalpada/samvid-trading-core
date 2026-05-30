"""Generate a deterministic execution-quality report from the audit chain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from execution_evidence import build_execution_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-log", default="data/execution_audit.jsonl")
    parser.add_argument("--json-out", default="data/execution_audit_report.json")
    parser.add_argument("--since-timestamp-ns", type=int, default=0)
    args = parser.parse_args()

    report = build_execution_evidence(
        args.audit_log,
        since_timestamp_ns=args.since_timestamp_ns,
    )
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
