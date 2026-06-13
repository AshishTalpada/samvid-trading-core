import sqlite3

import pytest

from paper_performance import build_paper_performance, establish_performance_baseline


def _build_db(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY,
                trading_mode TEXT,
                outcome TEXT,
                pnl_dollars REAL,
                net_pnl REAL,
                commission REAL,
                slippage REAL,
                r_multiple REAL
            )
            """
        )
    conn.close()


def _build_timestamped_db(path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE trades (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                trading_mode TEXT,
                outcome TEXT,
                pnl_dollars REAL,
                net_pnl REAL,
                commission REAL,
                slippage REAL,
                r_multiple REAL
            )
            """
        )
    conn.close()


def test_paper_performance_measures_net_quality_and_cost_drag(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "ibkr_paper", "WIN", 12.0, 10.0, 1.0, 1.0, 2.0),
                (2, "ibkr_paper", "LOSS", -4.0, -5.0, 0.5, 0.5, -1.0),
                (3, "live", "WIN", 500.0, 500.0, 0.0, 0.0, 5.0),
            ],
        )
    conn.close()

    report = build_paper_performance(path, starting_equity=100.0)
    metrics = report["metrics"]

    assert metrics["trades"] == 2
    assert metrics["net_pnl"] == 5.0
    assert metrics["gross_pnl"] == 8.0
    assert metrics["expectancy_net"] == 2.5
    assert metrics["profit_factor"] == 2.0
    assert metrics["cost_drag"] == 3.0
    assert metrics["max_drawdown_pct"] == 5 / 110


def test_paper_performance_handles_empty_history(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)

    report = build_paper_performance(path)

    assert report["metrics"]["trades"] == 0
    assert report["metrics"]["expectancy_net"] == 0.0
    assert report["metrics"]["profit_factor"] == 0.0
    assert report["window"]["calendar_days"] == 0.0


def test_paper_performance_reports_encrypted_optional_field_coverage(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "ibkr_paper", "WIN", "ciphertext", 10.0, 1.0, 0.5, "ciphertext"),
        )
    conn.close()

    metrics = build_paper_performance(path)["metrics"]

    assert metrics["trades"] == 1
    assert metrics["net_pnl"] == 10.0
    assert metrics["gross_pnl_samples"] == 0
    assert metrics["r_multiple_samples"] == 0


def test_paper_performance_can_start_from_clean_trade_id_baseline(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "ibkr_paper", "LOSS", -50.0, -50.0, 0.0, 0.0, -1.0),
                (2, "ibkr_paper", "WIN", 10.0, 10.0, 0.0, 0.0, 1.0),
            ],
        )
    conn.close()

    report = build_paper_performance(path, min_trade_id=2)

    assert report["window"]["min_trade_id"] == 2
    assert report["window"]["first_trade_id"] == 2
    assert report["window"]["last_trade_id"] == 2
    assert report["window"]["baseline_source"] == "explicit_or_full_history"
    assert report["metrics"]["trades"] == 1
    assert report["metrics"]["net_pnl"] == 10.0


def test_paper_performance_uses_stored_baseline_by_default(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "ibkr_paper", "LOSS", -50.0, -50.0, 0.0, 0.0, -1.0),
                (2, "ibkr_paper", "WIN", 10.0, 10.0, 0.0, 0.0, 1.0),
            ],
        )
    conn.close()
    baseline = establish_performance_baseline(path, reason="test baseline")
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (3, "ibkr_paper", "WIN", 20.0, 20.0, 0.0, 0.0, 2.0),
        )
    conn.close()

    report = build_paper_performance(path)

    assert baseline["min_trade_id"] == 3
    assert report["window"]["min_trade_id"] == 3
    assert report["window"]["baseline_source"] == "stored_system_state"
    assert report["metrics"]["trades"] == 1
    assert report["metrics"]["net_pnl"] == 20.0


def test_paper_performance_reports_timestamp_calendar_span(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_timestamped_db(path)
    with sqlite3.connect(path) as conn:
        conn.executemany(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "2026-01-01T14:30:00+00:00", "ibkr_paper", "WIN", 10, 10, 0, 0, 1),
                (2, "2026-01-31T14:30:00+00:00", "ibkr_paper", "LOSS", -5, -5, 0, 0, -1),
            ],
        )
    conn.close()

    report = build_paper_performance(path)

    assert report["window"]["timestamp_samples"] == 2
    assert report["window"]["calendar_days"] == 30.0
    assert report["window"]["first_trade_timestamp"] == "2026-01-01T14:30:00+00:00"
    assert report["window"]["last_trade_timestamp"] == "2026-01-31T14:30:00+00:00"


def test_paper_performance_baseline_requires_force_to_replace(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)
    establish_performance_baseline(path, reason="first")

    with pytest.raises(ValueError, match="already exists"):
        establish_performance_baseline(path, reason="second")

    replacement = establish_performance_baseline(path, reason="second", force=True)

    assert replacement["reason"] == "second"
