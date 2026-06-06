from backtest_engine import phase1_gate_report


def _stats(
    *,
    p_value: float = 0.01,
    profit_factor: float = 1.5,
    expectancy_net_usd: float = 0.25,
    sharpe_per_trade: float = 0.2,
    max_drawdown: float = -0.04,
) -> dict:
    return {
        "p_value": p_value,
        "profit_factor": profit_factor,
        "expectancy_net_usd": expectancy_net_usd,
        "sharpe_per_trade": sharpe_per_trade,
        "max_drawdown": max_drawdown,
    }


def test_phase1_gate_requires_majority_of_symbols_to_pass_all_metrics() -> None:
    report = phase1_gate_report(
        {
            "SPY": _stats(),
            "QQQ": _stats(),
            "IWM": _stats(profit_factor=1.0),
        }
    )

    assert report["passed"] is True
    assert report["required_passes"] == 2
    assert report["passed_symbols"] == ["SPY", "QQQ"]
    assert "profit_factor" in report["symbol_reports"]["IWM"]["blockers"][0]


def test_phase1_gate_blocks_high_p_value_negative_expectancy_and_deep_drawdown() -> None:
    report = phase1_gate_report(
        {
            "SPY": _stats(p_value=0.2),
            "QQQ": _stats(expectancy_net_usd=-0.01),
            "IWM": _stats(max_drawdown=-0.2),
        }
    )

    assert report["passed"] is False
    blockers = " ".join(
        blocker
        for symbol_report in report["symbol_reports"].values()
        for blocker in symbol_report["blockers"]
    )
    assert "p_value" in blockers
    assert "expectancy_net_usd" in blockers
    assert "max_drawdown" in blockers


def test_phase1_gate_fails_empty_results() -> None:
    report = phase1_gate_report({})

    assert report["passed"] is False
    assert report["required_passes"] == 1
