from resilience_layer import FailedOrder
from system_types import OrderIntent


def test_failed_order_timestamp_is_timezone_aware() -> None:
    order = FailedOrder(symbol="SPY", direction="BUY", shares=1, price=100.0)

    assert order.ts_first_fail.tzinfo is not None
    assert order.ts_first_fail.utcoffset() is not None


def test_order_intent_timestamp_is_timezone_aware() -> None:
    intent = OrderIntent(
        symbol="SPY",
        side="BUY",
        size_units=1.0,
        target_price=100.0,
        logic_signature="test",
    )

    assert intent.created_at.tzinfo is not None
    assert intent.created_at.utcoffset() is not None
