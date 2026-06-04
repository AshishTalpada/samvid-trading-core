from promotion_readiness import evaluate_promotion_readiness


def _ready_evidence() -> dict:
    return {
        "execution_evidence": {
            "audit": {"valid": True},
            "lineage": {
                "intents": 30,
                "filled_intents": 20,
                "matched_fills": 20,
                "overfilled_intents": 0,
                "underfilled_intents": 0,
                "unmatched_lineage_events": 0,
            },
            "costs": {
                "commission_reports": 20,
                "observed_slippage_events": 20,
            },
        },
        "reliability_probe": {"passed": True},
        "regime_replay": {"passed": True, "promotion_eligible": False},
        "soak_summary": {"passed": True, "cycles": [{}, {}, {}]},
        "paper_performance": {
            "source": "sqlite_closed_paper_trades",
            "window": {"baseline_source": "stored_system_state"},
            "metrics": {
                "trades": 30,
                "expectancy_net": 2.0,
                "profit_factor": 1.5,
                "max_drawdown_pct": 0.05,
            },
        },
    }


def test_promotion_readiness_accepts_complete_paper_evidence() -> None:
    report = evaluate_promotion_readiness(**_ready_evidence())

    assert report["approved"] is True
    assert report["blockers"] == []


def test_promotion_readiness_rejects_legacy_only_execution_history() -> None:
    evidence = _ready_evidence()
    evidence["execution_evidence"]["lineage"].update(
        {"intents": 0, "filled_intents": 0, "legacy_records_without_intent_id": 104}
    )
    evidence["execution_evidence"]["costs"].update(
        {"commission_reports": 0, "observed_slippage_events": 0}
    )

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "modern paper execution lineage requires 30 intents; found 0" in report["blockers"]
    assert "no modern paper fills recorded" in report["blockers"]


def test_promotion_readiness_rejects_incomplete_cost_coverage() -> None:
    evidence = _ready_evidence()
    evidence["execution_evidence"]["costs"]["commission_reports"] = 19
    evidence["execution_evidence"]["costs"]["observed_slippage_events"] = 19

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "commission coverage is incomplete for fill fragments" in report["blockers"]
    assert "slippage coverage is incomplete for fill fragments" in report["blockers"]


def test_promotion_readiness_rejects_fill_quantity_mismatches() -> None:
    evidence = _ready_evidence()
    evidence["execution_evidence"]["lineage"]["overfilled_intents"] = 1
    evidence["execution_evidence"]["lineage"]["underfilled_intents"] = 1

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "broker audit contains overfilled intents" in report["blockers"]
    assert "broker audit contains underfilled intents" in report["blockers"]


def test_promotion_readiness_rejects_weak_soak_or_replay() -> None:
    evidence = _ready_evidence()
    evidence["regime_replay"]["passed"] = False
    evidence["soak_summary"]["cycles"] = [{}, {}]

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "deterministic regime replay has not passed" in report["blockers"]
    assert "restart soak requires 3 passing cycles" in report["blockers"]


def test_promotion_readiness_rejects_weak_closed_paper_performance() -> None:
    evidence = _ready_evidence()
    evidence["paper_performance"]["metrics"].update(
        {
            "trades": 12,
            "expectancy_net": -0.25,
            "profit_factor": 0.8,
            "max_drawdown_pct": 0.15,
        }
    )

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "closed paper performance requires 30 trades; found 12" in report["blockers"]
    assert "closed paper expectancy is not positive after costs" in report["blockers"]
    assert "closed paper profit factor is below 1.20" in report["blockers"]
    assert "closed paper max drawdown exceeds 10.0%" in report["blockers"]


def test_promotion_readiness_rejects_unanchored_performance_window() -> None:
    evidence = _ready_evidence()
    evidence["paper_performance"]["window"]["baseline_source"] = "explicit_or_full_history"

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "paper performance artifact is not anchored to a stored baseline" in report["blockers"]
