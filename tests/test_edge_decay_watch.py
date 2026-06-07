"""Edge-decay watch must warm up safely and flag sustained losses for retirement."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "scripts", ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def test_edge_decay_warming_up_with_insufficient_history():
    from edge_decay_watch import evaluate_edge_decay

    result = evaluate_edge_decay([1.0, 2.0, -1.0])
    assert result["status"] == "WARMING_UP"
    assert result["days_observed"] == 3


def test_edge_decay_retires_on_five_consecutive_losses():
    from edge_decay_watch import evaluate_edge_decay

    series = [5.0] * 15 + [-3.0, -4.0, -2.0, -5.0, -1.0]  # 20 days, last 5 negative
    result = evaluate_edge_decay(series)
    assert result["days_observed"] == 20
    assert result["status"] == "RETIRE"


def test_edge_decay_healthy_on_steady_gains():
    from edge_decay_watch import evaluate_edge_decay

    series = [2.0, 2.2, 1.8, 2.1, 1.9] * 5  # 25 steady positive days
    result = evaluate_edge_decay(series)
    assert result["status"] in ("HEALTHY", "DECAY")  # never RETIRE on positive returns
    assert result["status"] != "RETIRE"


def test_daily_pnls_from_db_groups_by_calendar_day(tmp_path):
    from edge_decay_watch import daily_pnls_from_db

    db = tmp_path / "trading.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE trades (id INTEGER PRIMARY KEY, timestamp TEXT, trading_mode TEXT, "
        "outcome TEXT, net_pnl REAL, pnl_dollars REAL)"
    )
    conn.executemany(
        "INSERT INTO trades (timestamp, trading_mode, outcome, net_pnl, pnl_dollars) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("2026-01-01T10:00:00+00:00", "ibkr_paper", "WIN", 10.0, 10.0),
            ("2026-01-01T15:00:00+00:00", "ibkr_paper", "LOSS", -4.0, -4.0),
            ("2026-01-02T11:00:00+00:00", "paper", "WIN", 7.0, 7.0),
        ],
    )
    conn.commit()
    conn.close()

    daily = daily_pnls_from_db(db)
    assert daily == [6.0, 7.0]  # day1 net 10-4=6, day2 net 7


def test_daily_pnls_from_db_missing_db_returns_empty(tmp_path):
    from edge_decay_watch import daily_pnls_from_db

    assert daily_pnls_from_db(tmp_path / "does_not_exist.db") == []
