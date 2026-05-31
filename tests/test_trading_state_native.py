from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from trading_state import TradingState, TradingStateManager


@pytest.fixture(autouse=True)
def reset_trading_state() -> None:
    TradingStateManager._state = TradingState.ACTIVE
    TradingStateManager._reason = "test setup"
    yield
    TradingStateManager._state = TradingState.ACTIVE
    TradingStateManager._reason = "test cleanup"


def test_native_halt_signal_blocks_order_submission(monkeypatch) -> None:
    monkeypatch.setattr(TradingStateManager, "_native_halt_active", MagicMock(return_value=True))
    propagate = MagicMock()
    monkeypatch.setattr(TradingStateManager, "_set_native_halt", propagate)

    allowed, reason = TradingStateManager.allow_order()

    assert allowed is False
    assert reason == "TRADING HALTED: Native safety halt signal active"
    assert TradingStateManager.is_halted() is True
    propagate.assert_called_once_with(True)


def test_software_halt_propagates_to_native_signal(monkeypatch) -> None:
    propagate = MagicMock()
    monkeypatch.setattr(TradingStateManager, "_set_native_halt", propagate)

    TradingStateManager.halt("operator trip")

    assert TradingStateManager.is_halted() is True
    propagate.assert_called_once_with(True)


def test_manual_activation_clears_native_signal(monkeypatch) -> None:
    TradingStateManager._state = TradingState.HALTED
    propagate = MagicMock()
    monkeypatch.setattr(TradingStateManager, "_set_native_halt", propagate)

    TradingStateManager.activate("operator reset")

    assert TradingStateManager.is_active() is True
    propagate.assert_called_once_with(False)
