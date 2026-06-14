from backtest_engine import Trade, WalkForwardResult, aggregate_results, phase1_gate_report


def test_trade_return_is_net_of_commission() -> None:
    trade = Trade(
        symbol="SPY",
        entry_price=100.0,
        exit_price=101.0,
        entry_idx=1,
        exit_idx=2,
        side="LONG",
        size_usd=100.0,
        commission=2.0,
    )

    assert trade.gross_pnl_pct == 0.01
    assert trade.pnl_usd == -1.0
    assert trade.pnl_pct == -0.01


def test_drawdown_is_measured_against_starting_equity() -> None:
    result = WalkForwardResult(
        symbol="SPY",
        window_start=0,
        window_end=10,
        initial_capital=100.0,
        trades=[
            Trade("SPY", 100.0, 90.0, 1, 2, "LONG", 0.0, size_usd=100.0),
        ],
    )

    assert result.max_drawdown == -0.1


def test_aggregate_reports_window_stability_and_net_returns() -> None:
    profitable = WalkForwardResult(
        symbol="SPY",
        window_start=0,
        window_end=10,
        initial_capital=100.0,
        trades=[Trade("SPY", 100.0, 102.0, 1, 2, "LONG", 0.0, size_usd=100.0)],
    )
    losing = WalkForwardResult(
        symbol="SPY",
        window_start=10,
        window_end=20,
        initial_capital=100.0,
        trades=[Trade("SPY", 100.0, 99.0, 11, 12, "LONG", 0.0, size_usd=100.0)],
    )

    stats = aggregate_results([profitable, losing])

    assert stats["total_pnl_usd"] == 1.0
    assert stats["positive_window_rate"] == 0.5
    assert stats["max_drawdown"] == -0.0098


def test_phase1_gate_rejects_thin_or_unstable_samples() -> None:
    report = phase1_gate_report(
        {
            "SPY": {
                "p_value": 0.01,
                "profit_factor": 2.0,
                "expectancy_net_usd": 1.0,
                "sharpe_per_trade": 0.5,
                "max_drawdown": -0.02,
                "total_trades": 10,
                "positive_window_rate": 0.2,
            }
        }
    )

    assert report["passed"] is False
    blockers = " ".join(report["symbol_reports"]["SPY"]["blockers"])
    assert "total_trades" in blockers
    assert "positive_window_rate" in blockers
