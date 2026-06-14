from unittest.mock import MagicMock

from ops.maintenance import PredictiveMaintenanceAgent


def test_resource_breach_requires_consecutive_confirmation() -> None:
    agent = PredictiveMaintenanceAgent(confirmation_samples=2)
    agent.health_snapshot = MagicMock(
        return_value={"cpu_pct": 99.0, "ram_pct": 30.0, "disk_usage_pct": 40.0}
    )

    first = agent.evaluate()
    second = agent.evaluate()

    assert first["status"] == "DEGRADED"
    assert second["status"] == "CRITICAL"
    assert second["confirmed"] == ["cpu_pct"]


def test_recovery_resets_confirmation_counter() -> None:
    agent = PredictiveMaintenanceAgent(confirmation_samples=2)
    agent.health_snapshot = MagicMock(
        side_effect=[
            {"cpu_pct": 99.0, "ram_pct": 30.0, "disk_usage_pct": 40.0},
            {"cpu_pct": 20.0, "ram_pct": 30.0, "disk_usage_pct": 40.0},
            {"cpu_pct": 99.0, "ram_pct": 30.0, "disk_usage_pct": 40.0},
        ]
    )

    assert agent.evaluate()["status"] == "DEGRADED"
    assert agent.evaluate()["status"] == "ONLINE"
    assert agent.evaluate()["status"] == "DEGRADED"


def test_snapshot_uses_configured_project_drive(tmp_path) -> None:
    agent = PredictiveMaintenanceAgent(root_path=tmp_path)

    snapshot = agent.health_snapshot()

    assert {"cpu_pct", "ram_pct", "disk_usage_pct"} <= snapshot.keys()
