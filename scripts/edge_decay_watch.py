#!/usr/bin/env python3
"""Phase 4 edge-decay watch: detect alpha decay from the closed-trade record.

Feeds the per-day net PnL of closed paper/live trades into the existing
AlphaDecayWatchdog and reports HEALTHY / DECAY / RETIRE. Intended to be run on a
schedule (e.g. daily/weekly) rather than inline in the trading hot path, so it can
never destabilise live execution.

Usage:
    python scripts/edge_decay_watch.py
    python scripts/edge_decay_watch.py --db data/trading.db --strategy sovereign
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _path in (ROOT, SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def daily_pnls_from_db(
    db_path: str | Path = "data/trading.db",
    *,
    trading_modes: tuple[str, ...] = ("paper", "ibkr_paper"),
) -> list[float]:
    """Return chronological per-calendar-day net PnL from closed trades."""
    from paper_performance import _parse_timestamp

    path = Path(db_path)
    if not path.exists():
        return []
    placeholders = ",".join("?" for _ in trading_modes)
    with sqlite3.connect(str(path), timeout=60.0) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()}
        if not columns:
            return []
        ts_select = "timestamp" if "timestamp" in columns else "NULL"
        try:
            rows = conn.execute(
                f"""
                SELECT {ts_select}, COALESCE(net_pnl, pnl_dollars, 0)
                FROM trades
                WHERE outcome IN ('WIN', 'LOSS', 'BREAKEVEN')
                  AND trading_mode IN ({placeholders})
                ORDER BY id ASC
                """,
                tuple(trading_modes),
            ).fetchall()
        except sqlite3.OperationalError:
            return []

    daily: "OrderedDict[str, float]" = OrderedDict()
    for ts_raw, pnl in rows:
        parsed = _parse_timestamp(ts_raw)
        key = parsed.date().isoformat() if parsed else "unknown"
        daily[key] = daily.get(key, 0.0) + float(pnl or 0.0)
    return list(daily.values())


def evaluate_edge_decay(daily_pnls: list[float], *, strategy_id: str = "sovereign") -> dict[str, Any]:
    """Feed a chronological daily-PnL series into the watchdog and return its verdict."""
    from alpha_watchdog import AlphaDecayWatchdog

    watchdog = AlphaDecayWatchdog()
    for pnl in daily_pnls:
        watchdog.record(strategy_id, float(pnl))
    result = watchdog.evaluate(strategy_id, emit_log=False)
    result["days_observed"] = len(daily_pnls)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect alpha decay from the closed-trade record.")
    parser.add_argument("--db", default=str(ROOT / "data" / "trading.db"))
    parser.add_argument("--strategy", default="sovereign")
    args = parser.parse_args(argv)

    daily = daily_pnls_from_db(args.db)
    result = evaluate_edge_decay(daily, strategy_id=args.strategy)

    print("=" * 64)
    print("  EDGE-DECAY WATCH")
    print("=" * 64)
    print(f"  Strategy        : {args.strategy}")
    print(f"  Days observed   : {result['days_observed']}")
    print(f"  Status          : {result['status']}")
    print(f"  Fast Sharpe     : {result.get('fast_sharpe', 0.0)}")
    print(f"  Slow Sharpe     : {result.get('slow_sharpe', 0.0)}")
    if "decay_ratio" in result:
        print(f"  Decay ratio     : {result['decay_ratio']}")
    print("=" * 64)

    # Fail (non-zero) when the edge has decayed or the strategy should be retired.
    return 0 if result["status"] in ("HEALTHY", "WARMING_UP") else 2


if __name__ == "__main__":
    raise SystemExit(main())
