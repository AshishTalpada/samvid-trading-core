"""Preview or apply hash-verified trade-ledger repairs from broker execution evidence."""

from __future__ import annotations

import argparse
import json
import sqlite3

from execution_evidence import repair_trade_ledger_from_execution_audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/trading.db")
    parser.add_argument("--audit-log", default="data/execution_audit.jsonl")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--include-closed", action="store_true")
    args = parser.parse_args()
    outcomes = ("RECONCILIATION_REQUIRED",)
    if args.include_closed:
        outcomes += ("WIN", "LOSS", "BREAKEVEN")

    conn = sqlite3.connect(args.db, timeout=60.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
        repairs = repair_trade_ledger_from_execution_audit(
            conn,
            args.audit_log,
            outcomes=outcomes,
            apply=args.apply,
        )
    finally:
        conn.close()
    print(json.dumps({"applied": args.apply, "repairs": repairs}, indent=2))


if __name__ == "__main__":
    main()
