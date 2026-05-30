from unittest.mock import MagicMock

import pytest

from mind_experiment import MindExperiment
from strategy_promotion import evaluate_strategy_promotion


def test_strategy_promotion_requires_meaningful_sample() -> None:
    report = evaluate_strategy_promotion([2.0] * 5)

    assert report["approved"] is False
    assert "sample size 5/30" in report["reasons"]


def test_strategy_promotion_accepts_positive_controlled_shadow_results() -> None:
    report = evaluate_strategy_promotion([2.0, -1.0] * 15)

    assert report["approved"] is True
    assert report["metrics"]["trades"] == 30
    assert report["metrics"]["expectancy"] == pytest.approx(0.5)
    assert report["metrics"]["profit_factor"] == pytest.approx(2.0)


def test_strategy_promotion_rejects_excessive_loss_streak() -> None:
    report = evaluate_strategy_promotion(([2.0, -1.0] * 15) + ([-1.0] * 6))

    assert report["approved"] is False
    assert "loss streak 7 > 5" in report["reasons"]


@pytest.mark.asyncio
async def test_mind_experiment_refuses_five_trade_promotion() -> None:
    experiment = MindExperiment(MagicMock())
    await experiment._tool_run_shadow_test("entry_filter", "v2", {})
    experiment.active_experiments["entry_filter"]["performance_history"] = [2.0] * 5

    result = await experiment._tool_gate_feature("entry_filter", enabled=True)

    assert result["success"] is False
    assert "sample size 5/30" in result["error"]


@pytest.mark.asyncio
async def test_mind_experiment_promotes_only_verified_shadow_results() -> None:
    experiment = MindExperiment(MagicMock())
    await experiment._tool_run_shadow_test("entry_filter", "v2", {})
    experiment.active_experiments["entry_filter"]["performance_history"] = [2.0, -1.0] * 15

    result = await experiment._tool_gate_feature("entry_filter", enabled=True)

    assert result == {"success": True, "evidence_verified": True}
