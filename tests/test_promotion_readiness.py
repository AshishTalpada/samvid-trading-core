from promotion_readiness import evaluate_promotion_readiness


def _ready_evidence() -> dict:
    return {
        "execution_evidence": {
            "audit": {"valid": True},
            "lineage": {
                "intents": 30,
                "filled_intents": 20,
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
    assert "commission coverage is incomplete for modern fills" in report["blockers"]
    assert "slippage coverage is incomplete for modern fills" in report["blockers"]


def test_promotion_readiness_rejects_weak_soak_or_replay() -> None:
    evidence = _ready_evidence()
    evidence["regime_replay"]["passed"] = False
    evidence["soak_summary"]["cycles"] = [{}, {}]

    report = evaluate_promotion_readiness(**evidence)

    assert report["approved"] is False
    assert "deterministic regime replay has not passed" in report["blockers"]
    assert "restart soak requires 3 passing cycles" in report["blockers"]
