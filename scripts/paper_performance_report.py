"""Generate a cost-aware closed-paper-trade performance artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_performance import build_paper_performance, establish_performance_baseline  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/trading.db")
    parser.add_argument("--starting-equity", type=float, default=100_000.0)
    parser.add_argument("--min-trade-id", type=int)
    parser.add_argument("--set-baseline", action="store_true")
    parser.add_argument("--force-baseline", action="store_true")
    parser.add_argument("--baseline-reason", default="post-repair paper evidence baseline")
    parser.add_argument("--json-out", default="data/paper_performance_report.json")
    args = parser.parse_args()

    baseline = None
    if args.set_baseline:
        baseline = establish_performance_baseline(
            args.db,
            reason=args.baseline_reason,
            force=args.force_baseline,
        )
    report = build_paper_performance(
        args.db,
        starting_equity=args.starting_equity,
        min_trade_id=args.min_trade_id,
    )
    if baseline:
        report["baseline_established"] = baseline
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
