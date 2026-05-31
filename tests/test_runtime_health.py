import asyncio
import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from runtime_health import ComponentHealth, build_health_snapshot, market_data_health


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
    assert snapshot["readiness"] == "DEGRADED_READY"
    assert 75 <= snapshot["readiness_score"] < 100
    assert snapshot["action_items"]


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
    assert snapshot["readiness"] == "BLOCKED"
    assert snapshot["readiness_score"] < 75


def test_health_snapshot_scores_clean_stack_ready() -> None:
    snapshot = build_health_snapshot(
        [
            ComponentHealth("ibkr_execution", "CONNECTED", critical=True),
            ComponentHealth("dhatu", "ONLINE", critical=True),
            ComponentHealth("native_slm", "NATIVE", critical=False),
        ],
        mode="ibkr_paper",
        state="SCANNING",
    )

    assert snapshot["overall"] == "ONLINE"
    assert snapshot["readiness"] == "READY"
    assert snapshot["readiness_score"] == 100
    assert snapshot["action_items"] == []


def test_health_snapshot_with_paused_optional_component_stays_degraded_ready() -> None:
    snapshot = build_health_snapshot(
        [
            ComponentHealth("ibkr_execution", "CONNECTED", critical=True),
            ComponentHealth("dhatu", "ONLINE", critical=True),
            ComponentHealth("native_slm", "COMPAT", critical=False),
            ComponentHealth("tv_quotes", "PAUSED", "market closed", critical=False),
        ],
        mode="ibkr_paper",
        state="SCANNING",
    )

    assert snapshot["overall"] == "DEGRADED"
    assert snapshot["readiness"] == "DEGRADED_READY"
    assert snapshot["readiness_score"] >= 90


def test_market_data_health_pauses_cleanly_after_hours() -> None:
    health = market_data_health({}, market_open=False)

    assert health.status == "PAUSED"
    assert health.critical is False


def test_market_data_health_requires_recent_verified_bar() -> None:
    missing = market_data_health({}, market_open=True, now_monotonic=100.0)
    stale = market_data_health(
        {"SPY": 10.0},
        market_open=True,
        max_age_sec=30.0,
        now_monotonic=100.0,
    )
    fresh = market_data_health(
        {"SPY": 95.0, "QQQ": 90.0},
        market_open=True,
        max_age_sec=30.0,
        now_monotonic=100.0,
    )

    assert missing.status == "DELAYED"
    assert stale.status == "DELAYED"
    assert fresh.status == "ONLINE"
    assert "verified_symbols=2" in fresh.detail


def test_trading_system_snapshot_preserves_openbb_fallback_detail(monkeypatch) -> None:
    import main as main_mod

    system = main_mod.TradingSystem.__new__(main_mod.TradingSystem)
    system.mode = "ibkr_paper"
    system.trading_brain = SimpleNamespace(
        state=SimpleNamespace(name="STANDBY"),
        positions=[],
        _last_fresh_bar_at={},
    )
    system._openbb_provider = SimpleNamespace(
        health_status=lambda: (
            "FALLBACK",
            "OpenBB SDK unavailable; pipeline fallback provider=yfinance",
        )
    )
    system.dhatu_oracle = object()
    system.native_slm = None
    system.tv_quote_streamer = None
    system.hft_streamer = None
    monkeypatch.setattr(main_mod, "is_us_equity_market_open", lambda: False)
    monkeypatch.setattr(main_mod, "us_equity_session_status", lambda: "CLOSED")

    snapshot = system._build_runtime_health_snapshot(
        ibkr_value="connected",
        mt5_value="disconnected",
    )

    openbb = snapshot["components"]["openbb"]
    assert openbb["status"] == "FALLBACK"
    assert "pipeline fallback provider=yfinance" in openbb["detail"]
    assert "openbb" in snapshot["degraded"]


@pytest.mark.asyncio
async def test_runtime_health_snapshot_persists_and_publishes_immediately() -> None:
    import main as main_mod

    system = main_mod.TradingSystem.__new__(main_mod.TradingSystem)
    system.db_conn = sqlite3.connect(":memory:")
    system.db_conn.execute(
        "CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)"
    )
    system.db_lock = asyncio.Lock()
    system.ibkr_client = SimpleNamespace(isConnected=lambda: True)
    system.mt5_client = SimpleNamespace(
        terminal_info=lambda: SimpleNamespace(connected=True)
    )
    system.bus = SimpleNamespace(publish=AsyncMock())
    system._build_runtime_health_snapshot = MagicMock(
        return_value={"overall": "DEGRADED", "components": {"openbb": {"status": "FALLBACK"}}}
    )
    system._record_system_event = MagicMock()
    system._refresh_performance_summary = MagicMock()

    snapshot = await system._persist_runtime_health_snapshot(
        event_type="startup_health",
        message="Startup runtime health",
    )

    rows = dict(system.db_conn.execute("SELECT key, value FROM system_state"))
    assert snapshot == {"overall": "DEGRADED", "components": {"openbb": {"status": "FALLBACK"}}}
    assert rows["ibkr_status"] == "connected"
    assert rows["mt5_status"] == "connected"
    assert json.loads(rows["service_health"]) == snapshot
    assert int(rows["last_heartbeat"]) > 0
    system._record_system_event.assert_called_once_with(
        "startup_health",
        "Startup runtime health",
        agent="main",
        details=snapshot,
    )
    system.bus.publish.assert_awaited_once_with("system.health", snapshot)
    system._refresh_performance_summary.assert_called_once_with()
