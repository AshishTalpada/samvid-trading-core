from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from mind_architect import MindArchitect
from mind_bridge import MindBridge
from mind_experiment import MindExperiment
from mind_system import MindSystem


async def _wait_forever() -> None:
    await asyncio.Event().wait()


@pytest.mark.asyncio
async def test_architect_start_is_idempotent_and_stop_cancels_workers(monkeypatch) -> None:
    architect = MindArchitect(MindBridge(), vault=MagicMock())
    monkeypatch.setattr(architect, "_monitor_heartbeat", _wait_forever)
    monkeypatch.setattr(architect, "_process_dialogue", _wait_forever)

    await architect.start()
    await architect.start()
    await asyncio.sleep(0)

    assert len(architect._tasks) == 2
    await architect.stop()
    assert architect.is_running is False
    assert not architect._tasks


@pytest.mark.asyncio
async def test_experiment_start_is_idempotent_and_stop_cancels_worker(monkeypatch) -> None:
    experiment = MindExperiment(MindBridge())
    monkeypatch.setattr(experiment, "_monitor_shadow_tests", _wait_forever)

    await experiment.start()
    await experiment.start()
    await asyncio.sleep(0)

    assert len(experiment._tasks) == 1
    await experiment.stop()
    assert experiment.is_running is False
    assert not experiment._tasks


@pytest.mark.asyncio
async def test_system_mind_exposes_symmetric_lifecycle() -> None:
    system = MindSystem(MindBridge())

    await system.start()
    assert system.is_running is True
    await system.stop()
    assert system.is_running is False
