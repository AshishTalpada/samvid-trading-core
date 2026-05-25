import json

import pytest

from tv_quote_streamer import TVQuoteStreamer


def _frame(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"))
    return f"~m~{len(raw)}~m~{raw}"


def test_parse_messages_and_quote_payload() -> None:
    streamer = TVQuoteStreamer()
    streamer._build_symbol_maps(["SPY"])
    payload = {
        "m": "qsd",
        "p": [
            streamer.session_id,
            {
                "n": "AMEX:SPY",
                "s": "ok",
                "v": {
                    "lp": 525.25,
                    "bid": 525.24,
                    "ask": 525.26,
                    "last_volume": 100,
                    "ch": 1.25,
                    "chp": 0.24,
                    "market_status": "market",
                },
            },
        ],
    }

    messages = streamer.parse_messages(_frame(payload))
    assert messages == [payload]

    quote = streamer._quote_from_message(messages[0])
    assert quote is not None
    tick = quote.to_tick_payload()
    assert tick["source"] == "TradingView_WS"
    assert tick["symbol"] == "SPY"
    assert tick["price"] == pytest.approx(525.25)
    assert tick["bid"] == pytest.approx(525.24)
    assert tick["ask"] == pytest.approx(525.26)


@pytest.mark.asyncio
async def test_publish_quote_emits_tick_and_candle_pulse() -> None:
    class FakeBus:
        def __init__(self) -> None:
            self.events = []

        async def publish(self, topic, payload) -> None:
            self.events.append((topic, payload))

    bus = FakeBus()
    streamer = TVQuoteStreamer(bus=bus)
    streamer._last_candle_pulse = 0.0
    quote = streamer._quote_from_message(
        {
            "m": "qsd",
            "p": [
                streamer.session_id,
                {"n": "NASDAQ:NVDA", "v": {"lp": 900.0, "bid": 899.9, "ask": 900.1}},
            ],
        }
    )

    assert quote is not None
    await streamer._publish_quote(quote)

    topics = [topic for topic, _payload in bus.events]
    assert "tick.hft" in topics
    assert "candle.batch" in topics
    tick_payload = next(payload for topic, payload in bus.events if topic == "tick.hft")
    assert tick_payload["symbol"] == "NVDA"
    assert tick_payload["source"] == "TradingView_WS"
