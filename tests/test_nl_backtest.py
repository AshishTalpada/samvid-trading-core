import numpy as np
import pytest

from testing.nl_backtest import NaturalLanguageBacktester


def test_parser_builds_constrained_sma_strategy() -> None:
    backtester = NaturalLanguageBacktester()

    spec = backtester.parse_query("Buy when price crosses above the 20 SMA; hold 5 bars")

    assert spec.side == "LONG"
    assert spec.indicator == "SMA"
    assert spec.operator == "cross_above"
    assert spec.threshold == 20
    assert spec.hold_bars == 5


def test_backtest_uses_real_data_instead_of_fixed_results() -> None:
    backtester = NaturalLanguageBacktester(round_trip_cost_bps=0.0)
    rising = np.linspace(100.0, 150.0, 300)
    falling = rising[::-1]

    rising_result = backtester.run_backtest(
        "Buy when price is above 20 SMA hold 5 bars",
        {"close": rising, "open": rising},
    )
    falling_result = backtester.run_backtest(
        "Buy when price is above 20 SMA hold 5 bars",
        {"close": falling, "open": falling},
    )

    assert rising_result["trades"] > 0
    assert rising_result["total_return"] > 0.0
    assert falling_result["trades"] == 0
    assert rising_result != falling_result


def test_round_trip_cost_is_applied() -> None:
    prices = np.linspace(100.0, 101.0, 300)
    free = NaturalLanguageBacktester(round_trip_cost_bps=0.0).run_backtest(
        "Buy when price is above 20 SMA hold 2 bars", {"prices": prices}
    )
    costly = NaturalLanguageBacktester(round_trip_cost_bps=50.0).run_backtest(
        "Buy when price is above 20 SMA hold 2 bars", {"prices": prices}
    )

    assert costly["total_return"] < free["total_return"]


def test_unsupported_strategy_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="unsupported strategy"):
        NaturalLanguageBacktester().run_backtest(
            "Make money whenever the market feels good", {"prices": np.arange(100.0)}
        )
