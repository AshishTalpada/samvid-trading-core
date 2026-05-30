from regime_replay import ReplayScenario, run_regime_replay_pack


def test_default_regime_replay_covers_normal_and_freeze_paths() -> None:
    report = run_regime_replay_pack()

    assert report["passed"] is True
    assert report["promotion_eligible"] is False
    assert report["coverage"]["missing_regimes"] == []
    assert report["policy_failures"] == []
    policy_by_name = {scenario["name"]: scenario["policy"] for scenario in report["scenarios"]}
    assert policy_by_name["trend_up_control"] == "NORMAL"
    assert policy_by_name["flash_crash_freeze"] == "FREEZE"
    assert policy_by_name["drawdown_freeze"] == "FREEZE"


def test_regime_replay_never_claims_synthetic_promotion_eligibility() -> None:
    report = run_regime_replay_pack()

    assert report["promotion_eligible"] is False
    assert "never authorize live strategy promotion" in report["operator_note"]


def test_regime_replay_fails_when_required_coverage_is_missing() -> None:
    report = run_regime_replay_pack(
        [
            ReplayScenario(
                name="bull_only",
                regime="BULL",
                pnl_values=(2.0, -1.0) * 15,
                vix=16.0,
                drawdown_pct=0.01,
                expected_policy="NORMAL",
            )
        ]
    )

    assert report["passed"] is False
    assert "VOLATILE" in report["coverage"]["missing_regimes"]


def test_regime_replay_fails_when_policy_behavior_changes() -> None:
    report = run_regime_replay_pack(
        [
            ReplayScenario(
                name="unexpected_policy",
                regime="BULL",
                pnl_values=(2.0, -1.0) * 15,
                vix=16.0,
                drawdown_pct=0.01,
                expected_policy="FREEZE",
            )
        ]
    )

    assert report["passed"] is False
    assert report["policy_failures"] == ["unexpected_policy"]
