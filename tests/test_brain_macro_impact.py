from brain import TradingBrain


def _brain_with_modifier(value: float) -> TradingBrain:
    brain = object.__new__(TradingBrain)
    brain._oracle_risk_modifier = value
    return brain


def test_repeated_bearish_macro_pulses_do_not_compound() -> None:
    brain = _brain_with_modifier(1.0)
    payload = {"impact": "BEARISH", "status": "ONLINE"}

    assert brain._apply_macro_impact(payload) is True
    assert brain._oracle_risk_modifier == 0.8
    assert brain._apply_macro_impact(payload) is False
    assert brain._oracle_risk_modifier == 0.8


def test_bullish_macro_does_not_override_defensive_modifier() -> None:
    brain = _brain_with_modifier(0.5)

    assert brain._apply_macro_impact({"impact": "BULLISH", "status": "ONLINE"}) is False
    assert brain._oracle_risk_modifier == 0.5


def test_unavailable_macro_feed_is_ignored() -> None:
    brain = _brain_with_modifier(1.0)

    assert brain._apply_macro_impact({"impact": "BEARISH", "status": "UNAVAILABLE"}) is False
    assert brain._oracle_risk_modifier == 1.0
