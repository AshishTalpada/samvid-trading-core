import json
import sqlite3
from types import SimpleNamespace

import pytest

from api_server import APIServer


def _server_with_snapshot(overall: str) -> APIServer:
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)"
    )
    db.execute(
        "INSERT INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
        (
            "service_health",
            json.dumps({"overall": overall, "readiness": "DEGRADED_READY"}),
            "2026-05-31 06:30:00",
        ),
    )
    db.commit()

    brain = SimpleNamespace(
        contrarian_agent=object(),
        chaos_agent=object(),
        contagion_sentinel=object(),
        audit_agent=object(),
    )
    server = APIServer.__new__(APIServer)
    server.system = SimpleNamespace(
        bus=object(),
        db_conn=db,
        trading_brain=brain,
    )
    return server


def test_api_health_payload_includes_authoritative_degraded_snapshot() -> None:
    server = _server_with_snapshot("DEGRADED")

    payload = server._build_health_payload()

    assert payload["status"] == "DEGRADED"
    assert payload["production"]["overall"] == "DEGRADED"
    assert payload["production"]["updated_at"] == "2026-05-31 06:30:00"
    assert payload["components"]["advisory_agents"] == {
        "contrarian_agent": "UP",
        "chaos_agent": "UP",
        "contagion_sentinel": "UP",
        "audit_agent": "UP",
    }


def test_api_health_payload_marks_production_offline_as_down() -> None:
    server = _server_with_snapshot("OFFLINE")

    payload = server._build_health_payload()

    assert payload["status"] == "DOWN"
    assert payload["production"]["overall"] == "OFFLINE"


def test_api_state_collection_latency_is_measured(monkeypatch) -> None:
    monkeypatch.setattr("api_server.time.perf_counter", lambda: 10.012345)
    health: dict = {}

    APIServer._annotate_collection_latency(health, 10.0)

    assert health["latency_ms"] == pytest.approx(12.345)
    assert health["latency_source"] == "api_state_collection"


def test_operator_component_probes_contain_optional_client_failures() -> None:
    class BrokenIBKR:
        def isConnected(self) -> bool:
            raise RuntimeError("socket closed")

    class BrokenMT5:
        def terminal_info(self):
            raise RuntimeError("terminal unavailable")

    server = APIServer.__new__(APIServer)
    server.system = SimpleNamespace(
        ibkr_client=BrokenIBKR(),
        mt5_client=BrokenMT5(),
        questdb=SimpleNamespace(is_active=True),
        dhatu_oracle=object(),
        trading_brain=SimpleNamespace(is_running=True),
    )

    statuses = server._operator_component_statuses()

    assert statuses == {
        "ibkr": "ERROR",
        "mt5": "ERROR",
        "qdb": "ONLINE",
        "dhatu": "ONLINE",
        "brain": "ONLINE",
        "sovereign": "ONLINE",
    }
