from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_remote import TelegramRemote


def _remote() -> TelegramRemote:
    with patch("src.telegram_remote.Vault.get", return_value="test"):
        remote = TelegramRemote()
    remote.bus = MagicMock()
    remote.bus.publish = AsyncMock()
    return remote


@pytest.mark.asyncio
async def test_trade_events_update_remote_snapshot() -> None:
    remote = _remote()

    await remote._update_trade_entry({"symbol": "spy"})
    await remote._update_trade_entry({"symbol": "SPY"})
    await remote._update_stats(
        {
            "symbol": "SPY",
            "pnl": 12.5,
            "exit_type": "TARGET_HIT",
            "r_multiple": 1.25,
            "shares_remaining": 0,
        }
    )

    assert remote.positions_count == 0
    assert remote.session_realized_pnl == 12.5
    assert remote.last_exit == {
        "symbol": "SPY",
        "pnl": 12.5,
        "exit_type": "TARGET_HIT",
        "r_multiple": 1.25,
    }


@pytest.mark.asyncio
async def test_invalid_exit_pnl_does_not_corrupt_snapshot() -> None:
    remote = _remote()

    await remote._update_stats({"symbol": "SPY", "pnl": float("nan")})
    await remote._update_stats({"symbol": "SPY", "pnl": "invalid"})

    assert remote.session_realized_pnl == 0.0
    assert remote.last_exit is None
