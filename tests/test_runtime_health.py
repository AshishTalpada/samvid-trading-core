from runtime_health import ComponentHealth, build_health_snapshot


def test_health_snapshot_marks_degraded_for_paused_free_feed() -> None:
    snapshot = build_health_snapshot(
        [
            ComponentHealth("ibkr_execution", "CONNECTED", critical=True),
            ComponentHealth("tv_quotes", "PAUSED", "market closed", critical=False),
            ComponentHealth("native_slm", "FALLBACK", "safe deterministic mode", critical=False),
        ],
        mode="ibkr_paper",
        state="SCANNING",
    )

    assert snapshot["overall"] == "DEGRADED"
    assert "tv_quotes" in snapshot["degraded"]
    assert "native_slm" in snapshot["degraded"]
    assert snapshot["critical_offline"] == []


def test_health_snapshot_marks_offline_when_critical_component_is_down() -> None:
    snapshot = build_health_snapshot(
        [
            ComponentHealth("ibkr_execution", "OFFLINE", critical=True),
            ComponentHealth("dhatu", "ONLINE", critical=True),
        ],
        mode="ibkr_paper",
        state="STANDBY",
    )

    assert snapshot["overall"] == "OFFLINE"
    assert snapshot["critical_offline"] == ["ibkr_execution"]
