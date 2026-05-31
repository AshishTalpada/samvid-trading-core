import asyncio
from collections import deque
from types import SimpleNamespace
from unittest.mock import MagicMock

from brain import TradingBrain
from brain_fsm import TradingState


def test_brain_tick_records_realtime_pipeline_cache() -> None:
    pipeline = SimpleNamespace(record_realtime_tick=MagicMock())
    brain = SimpleNamespace(
        last_tick_prices={},
        last_tick_bids={},
        last_tick_asks={},
        data_pipeline=pipeline,
        spy_buffer=deque(maxlen=200),
        new_tick_event=asyncio.Event(),
        state=TradingState.STANDBY,
    )
    payload = {
        "symbol": "SPY",
        "price": 525.25,
        "bid": 525.24,
        "ask": 525.26,
        "source": "TradingView_WS",
    }

    asyncio.run(TradingBrain.on_tick(brain, payload))

    assert brain.last_tick_prices["SPY"] == 525.25
    assert brain.new_tick_event.is_set()
    pipeline.record_realtime_tick.assert_called_once_with(payload)
