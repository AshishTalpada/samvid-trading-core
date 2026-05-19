import json
from datetime import datetime, timezone

from src.sovereign_task import SovereignTask, TaskManager
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
