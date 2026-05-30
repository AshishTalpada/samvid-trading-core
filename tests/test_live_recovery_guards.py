import json
from datetime import datetime, timezone

from src.sovereign_task import SovereignTask, TaskManager, TaskStatus
from src.system_types import Position


def test_position_normalizes_string_timestamps() -> None:
    pos = Position(
        symbol="SPY",
        qty=1,
        entry_price=500.0,
        entry_time="2026-05-19T16:55:06.000000+00:00",
        target_exit_time="2026-05-20T16:55:06.000000+00:00",
    )

    assert isinstance(pos.entry_time, datetime)
    assert pos.entry_time.tzinfo is not None
    assert pos.entry_time == datetime(2026, 5, 19, 16, 55, 6, tzinfo=timezone.utc)
    assert isinstance(pos.target_exit_time, datetime)
    assert pos.target_exit_time.tzinfo is not None


def test_task_registry_preserves_phase_on_restore(tmp_path) -> None:
    registry = tmp_path / "active_tasks.json"
    task = SovereignTask("t_SPY_1", "trade", "Executing SPY Trade", {})
    task.set_phase("VETTING", "checking cache and agent quorum")

    registry.write_text(json.dumps({"t_SPY_1": task.to_dict()}), encoding="utf-8")

    manager = TaskManager(registry_path=str(registry))

    restored = manager.tasks["t_SPY_1"]
    assert restored.status_summary == "VETTING: checking cache and agent quorum"
    assert restored.to_dict()["phase"] == restored.status_summary


def test_task_registry_can_retire_active_tasks_on_live_restore(tmp_path) -> None:
    registry = tmp_path / "active_tasks.json"
    task = SovereignTask("t_QQQ_1", "trade", "Executing QQQ Trade", {})
    task.set_phase("VETTING", "checking cache and agent quorum")
    registry.write_text(json.dumps({"t_QQQ_1": task.to_dict()}), encoding="utf-8")

    manager = TaskManager(registry_path=str(registry), retire_active_on_restore=True)

    restored = manager.tasks["t_QQQ_1"]
    assert restored.status == TaskStatus.KILLED
    assert restored.status_summary.startswith("ORPHANED:")


def test_task_manager_symbol_gate_blocks_active_task(tmp_path) -> None:
    manager = TaskManager(registry_path=str(tmp_path / "active_tasks.json"))

    task = manager.spawn_trade("SPY", {"pattern": "Descending Triangle"})

    gate = manager.get_symbol_gate("SPY")

    assert gate is not None
    gate_kind, gate_task, remaining = gate
    assert gate_kind == "active"
    assert gate_task is task
    assert remaining == 0.0


def test_task_manager_symbol_gate_blocks_recent_veto(tmp_path) -> None:
    manager = TaskManager(registry_path=str(tmp_path / "active_tasks.json"))
    task = manager.spawn_trade("QQQ", {"pattern": "Descending Triangle"})
    task.transition(TaskStatus.KILLED)

    gate = manager.get_symbol_gate("QQQ", terminal_cooldown_seconds=300.0)

    assert gate is not None
    gate_kind, gate_task, remaining = gate
    assert gate_kind == "cooldown"
    assert gate_task is task
    assert 0.0 < remaining <= 300.0
