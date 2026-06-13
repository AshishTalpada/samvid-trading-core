import asyncio

import pytest

from src.intelligence_bus import SharedIntelligenceBus


class Recorder:
    def __init__(self) -> None:
        self.payloads: list[dict] = []
        self.called = asyncio.Event()

    async def handle(self, payload: dict) -> None:
        self.payloads.append(payload)
        self.called.set()


@pytest.mark.asyncio
async def test_bound_callback_registration_is_idempotent_and_removable() -> None:
    bus = SharedIntelligenceBus()
    recorder = Recorder()
    bus.on("test.event", recorder.handle)
    bus.on("test.event", recorder.handle)

    await bus.publish("test.event", {"value": 1})
    await asyncio.wait_for(recorder.called.wait(), timeout=1.0)
    assert recorder.payloads == [{"value": 1}]

    recorder.called.clear()
    bus.off("test.event", recorder.handle)
    await bus.publish("test.event", {"value": 2})
    await asyncio.sleep(0.05)

    assert recorder.payloads == [{"value": 1}]
    assert bus._callback_workers == {}


@pytest.mark.asyncio
async def test_callback_exception_balances_worker_queue() -> None:
    bus = SharedIntelligenceBus()

    async def failing_handler(payload: dict) -> None:
        raise RuntimeError(str(payload))

    bus.on("test.error", failing_handler)
    worker_queue, _ = bus._callback_workers[bus._handler_key(failing_handler)]

    await bus.publish("test.error", {"value": 1})
    await asyncio.sleep(0.05)
    await asyncio.wait_for(worker_queue.join(), timeout=1.0)

    bus.off("test.error", failing_handler)
