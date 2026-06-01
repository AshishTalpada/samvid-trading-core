from unittest.mock import AsyncMock

import pytest

from dms import DMSMonitor


class _OfflineIBKR:
    def isConnected(self) -> bool:
        return False


class _OnlineIBKR:
    def isConnected(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_dms_reports_degraded_when_required_ibkr_is_offline() -> None:
    monitor = DMSMonitor(
        bot_token="test",
        chat_id="test",
        ibkr_client=_OfflineIBKR(),
        requires_ibkr_connection=True,
    )
    monitor._send_telegram_message = AsyncMock(return_value=True)

    await monitor.send_status_ok()

    message = monitor._send_telegram_message.await_args.args[0]
    assert "EXECUTION OFFLINE" in message
    assert "IBKR API:</b> offline" in message
    assert "All intelligence nodes nominal" not in message


@pytest.mark.asyncio
async def test_dms_reports_operational_when_required_ibkr_is_online() -> None:
    monitor = DMSMonitor(
        bot_token="test",
        chat_id="test",
        ibkr_client=_OnlineIBKR(),
        requires_ibkr_connection=True,
    )
    monitor._send_telegram_message = AsyncMock(return_value=True)

    await monitor.send_status_ok()

    message = monitor._send_telegram_message.await_args.args[0]
    assert "OPERATIONAL" in message
    assert "IBKR API:</b> connected" in message
