from __future__ import annotations

import asyncio

import pytest

from mind_bridge import MindBridge
from mind_evolution import MindEvolution


@pytest.mark.asyncio
async def test_equity_fetch_requires_authoritative_broker_value(tmp_path) -> None:
    bridge = MindBridge()
    evolution = MindEvolution(bridge, db_path=str(tmp_path / "mind.db"))

    async def account_status(account_type: str) -> dict:
        return {
            "equity": 950_000.0,
            "unrealized_pnl": 0.0,
            "equity_authoritative": False,
        }

    bridge.register_tool("get_account_status", account_status)

    assert await evolution._fetch_current_equity() is None


@pytest.mark.asyncio
async def test_equity_fetch_accepts_authoritative_broker_value(tmp_path) -> None:
    bridge = MindBridge()
    evolution = MindEvolution(bridge, db_path=str(tmp_path / "mind.db"))

    async def account_status(account_type: str) -> dict:
        return {
            "equity": 950_000.0,
            "unrealized_pnl": 100.0,
            "equity_authoritative": True,
        }

    bridge.register_tool("get_account_status", account_status)

    assert await evolution._fetch_current_equity() == 949_985.0


@pytest.mark.asyncio
async def test_threshold_optimizer_requires_enough_evidence(tmp_path) -> None:
    evolution = MindEvolution(MindBridge(), db_path=str(tmp_path / "mind.db"))

    result = await evolution._tool_optimize_thresholds(
        "breakout",
        {"trades": 12, "win_rate": 0.4, "current_threshold": 0.8},
    )

    assert result["status"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.asyncio
async def test_threshold_optimizer_returns_bounded_shadow_proposal(tmp_path) -> None:
    evolution = MindEvolution(MindBridge(), db_path=str(tmp_path / "mind.db"))

    result = await evolution._tool_optimize_thresholds(
        "breakout",
        {
            "trades": 100,
            "win_rate": 0.30,
            "current_threshold": 0.93,
            "target_win_rate": 0.60,
        },
    )

    assert result["status"] == "PROPOSED"
    assert result["proposed_threshold"] == 0.95
    assert result["requires_shadow_validation"] is True


@pytest.mark.asyncio
async def test_strategy_evolution_never_claims_live_application(tmp_path) -> None:
    evolution = MindEvolution(MindBridge(), db_path=str(tmp_path / "mind.db"))

    result = await evolution._tool_evolve_strategy("breakout", {"threshold": 0.8})

    assert result["success"] is True
    assert result["status"] == "PENDING_SHADOW_VALIDATION"
    assert result["applied"] is False


@pytest.mark.asyncio
async def test_stop_cancels_evolution_workers(tmp_path, monkeypatch) -> None:
    evolution = MindEvolution(MindBridge(), db_path=str(tmp_path / "mind.db"))
    monkeypatch.setattr(evolution, "_monitor_equity_peaks", _wait_forever)
    monkeypatch.setattr(evolution, "_process_strategic_dialogue", _wait_forever)
    monkeypatch.setattr(evolution, "_autonomous_heuristic_refinement", _wait_forever)

    await evolution.start()
    await asyncio.sleep(0)
    await evolution.stop()

    assert evolution.is_running is False
    assert not evolution._tasks


async def _wait_forever() -> None:
    await asyncio.Event().wait()
