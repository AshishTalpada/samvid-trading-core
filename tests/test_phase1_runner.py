import asyncio
import sqlite3

import pytest

from phase1_runner import (
    Phase1Coverage,
    _collect_data_coverage,
    _coverage_summary,
    run_backtest,
)


def _make_ohlcv_db(path, rows_by_symbol: dict[str, int]) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE ohlcv (symbol TEXT, timestamp TEXT, open REAL, high REAL, "
            "low REAL, close REAL, volume REAL)"
        )
        for symbol, count in rows_by_symbol.items():
            rows = [
                (symbol, str(i), 100.0, 101.0, 99.0, 100.5, 1000.0)
                for i in range(count)
            ]
            conn.executemany("INSERT INTO ohlcv VALUES (?,?,?,?,?,?,?)", rows)


def test_phase1_data_coverage_counts_every_symbol(tmp_path) -> None:
    db = tmp_path / "trading.db"
    _make_ohlcv_db(db, {"SPY": 5, "QQQ": 3})

    coverage = asyncio.run(_collect_data_coverage(str(db), ["SPY", "QQQ", "IWM"], 4))

    assert [(item.symbol, item.bars, item.ready) for item in coverage] == [
        ("SPY", 5, True),
        ("QQQ", 3, False),
        ("IWM", 0, False),
    ]


def test_phase1_coverage_summary_marks_missing_symbols() -> None:
    summary = _coverage_summary(
        [
            Phase1Coverage(symbol="SPY", bars=10, min_bars=10),
            Phase1Coverage(symbol="QQQ", bars=9, min_bars=10),
        ]
    )

    assert "SPY=10/10 OK" in summary
    assert "QQQ=9/10 MISSING" in summary


def test_run_backtest_fails_closed_when_history_is_insufficient(tmp_path) -> None:
    db = tmp_path / "trading.db"
    _make_ohlcv_db(db, {"SPY": 5, "QQQ": 5})

    with pytest.raises(SystemExit) as exc:
        asyncio.run(
            run_backtest(
                db_path=str(db),
                symbols=["SPY", "QQQ", "IWM"],
                min_bars=10,
                allow_backfill=False,
            )
        )

    assert exc.value.code == 1
