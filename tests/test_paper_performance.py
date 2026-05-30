import sqlite3

from paper_performance import build_paper_performance


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


def test_paper_performance_reports_encrypted_optional_field_coverage(tmp_path) -> None:
    path = tmp_path / "trading.db"
    _build_db(path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "ibkr_paper", "WIN", "ciphertext", 10.0, 1.0, 0.5, "ciphertext"),
        )

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

    report = build_paper_performance(path, min_trade_id=2)

    assert report["window"] == {
        "min_trade_id": 2,
        "first_trade_id": 2,
        "last_trade_id": 2,
    }
    assert report["metrics"]["trades"] == 1
    assert report["metrics"]["net_pnl"] == 10.0
