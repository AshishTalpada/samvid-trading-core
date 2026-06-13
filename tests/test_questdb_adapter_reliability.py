import asyncio
from unittest.mock import AsyncMock

import pytest

from src.questdb_adapter import QuestDBAdapter


@pytest.mark.asyncio
async def test_simulated_mode_buffers_records_until_reconnect() -> None:
    adapter = QuestDBAdapter(enabled=True)
    adapter.is_simulated = True
    adapter._next_reconnect_attempt = float("inf")
    adapter._connect = AsyncMock()
    adapter._worker_task = asyncio.create_task(adapter._worker())
    adapter._started = True

    adapter.log_event("runtime_health", {"online": False})
    await asyncio.sleep(0.05)

    assert adapter._queue.qsize() == 1
    adapter._connect.assert_not_awaited()
    await adapter.stop()
    await asyncio.wait_for(adapter._queue.join(), timeout=0.5)


@pytest.mark.asyncio
async def test_stop_balances_buffered_queue_accounting() -> None:
    adapter = QuestDBAdapter(enabled=True)
    adapter.log_tick("SPY", 100.0, 10.0)
    adapter.log_trade("SPY", "BUY", 100.0, 1.0, "test")

    await adapter.stop()

    assert adapter._queue.empty()
    await asyncio.wait_for(adapter._queue.join(), timeout=0.5)


def test_repeated_connect_failures_enter_scheduled_simulated_mode() -> None:
    adapter = QuestDBAdapter(enabled=True)

    delays = [adapter._record_connection_failure(100.0) for _ in range(3)]

    assert delays == [5.0, 10.0, 20.0]
    assert adapter.is_simulated is True
    assert adapter._next_reconnect_attempt == 400.0
