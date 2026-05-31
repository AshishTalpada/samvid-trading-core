import asyncio
import logging
import sys
from types import SimpleNamespace

import pytest

from time_sync import TimeSync


@pytest.fixture(autouse=True)
def restore_time_sync_state():
    original_servers = TimeSync.NTP_SERVERS
    original_offset = TimeSync._offset
    yield
    TimeSync.NTP_SERVERS = original_servers
    TimeSync._offset = original_offset


@pytest.mark.asyncio
async def test_ntp_servers_are_probed_concurrently(monkeypatch) -> None:
    started: set[str] = set()
    both_started = asyncio.Event()
    TimeSync.NTP_SERVERS = ["ntp-a.test", "ntp-b.test"]

    async def fake_query(cls, server: str) -> tuple[str, float]:
        started.add(server)
        if len(started) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.1)
        return server, 0.125 if server == "ntp-a.test" else 0.250

    monkeypatch.setattr(TimeSync, "_query_ntp_server", classmethod(fake_query))

    assert await TimeSync.sync() is True
    assert started == {"ntp-a.test", "ntp-b.test"}
    assert TimeSync.get_offset() == pytest.approx(0.125)


@pytest.mark.asyncio
async def test_ntp_failure_uses_http_fallback_without_per_host_warning(monkeypatch, caplog) -> None:
    TimeSync.NTP_SERVERS = ["ntp-a.test", "ntp-b.test"]

    async def fail_query(cls, server: str) -> tuple[str, float]:
        raise TimeoutError(server)

    class FailedHead:
        async def __aenter__(self):
            raise OSError("offline")

        async def __aexit__(self, *_args) -> None:
            return None

    class FakeSession:
        def head(self, *_args, **_kwargs) -> FailedHead:
            return FailedHead()

    class FakeSovereignSession:
        @staticmethod
        async def get_session() -> FakeSession:
            return FakeSession()

    monkeypatch.setattr(TimeSync, "_query_ntp_server", classmethod(fail_query))
    monkeypatch.setitem(
        sys.modules,
        "session_manager",
        SimpleNamespace(SovereignSession=FakeSovereignSession),
    )

    with caplog.at_level(logging.WARNING):
        assert await TimeSync.sync() is False

    assert "NTP UDP sync unavailable across 2/2 servers" in caplog.text
    assert "HTTP Time fallback failed: offline" in caplog.text
    assert "Failed to sync with ntp-a.test" not in caplog.text
