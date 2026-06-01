from pathlib import Path

import pytest

from agent_c_ibkr import BlackSwanProtocol
from brain_data import DataProvider
from scripts.active_hours_soak import ActiveHoursSyntheticMarket, run_active_hours_soak


def test_active_hours_tape_models_spreads_and_black_swan_segment() -> None:
    market = ActiveHoursSyntheticMarket(seed=7)

    regime, vix, quotes = market.step(progress=0.60, tick_hz=4.0)

    assert regime == "VOLATILE"
    assert BlackSwanProtocol().check(vix=vix, drawdown_pct=0.0) == "FREEZE"
    assert len(quotes) == len(DataProvider.EXECUTION_WATCHLIST)
    assert all(quote["bid"] < quote["price"] < quote["ask"] for quote in quotes)


@pytest.mark.asyncio
async def test_active_hours_short_soak_exercises_execution_and_freeze(tmp_path: Path) -> None:
    report = await run_active_hours_soak(
        duration_sec=3.0,
        tick_hz=10.0,
        report_sec=10.0,
        signal_interval_sec=0.1,
        max_hold_sec=0.3,
        seed=11,
        json_out=tmp_path / "active_hours_soak.json",
    )

    assert report["passed"] is True
    assert report["stats"]["entries_filled"] > 0
    assert report["stats"]["exits_filled"] > 0
    assert report["stats"]["signals_frozen"] > 0
    assert report["execution"]["lineage"]["intent_fill_rate"] == 1.0
