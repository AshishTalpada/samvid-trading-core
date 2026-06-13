import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mind_ghost import MindGhost


def _ghost() -> MindGhost:
    bridge = MagicMock()
    bridge.bus = None
    bridge.broadcast = AsyncMock()
    bridge.call_tool = AsyncMock()
    return MindGhost(bridge=bridge)


def test_probe_backoff_uses_single_exponential_sequence() -> None:
    ghost = _ghost()

    assert [ghost._probe_backoff_delay("IBKR", attempt) for attempt in range(1, 7)] == [
        30.0,
        60.0,
        120.0,
        240.0,
        480.0,
        480.0,
    ]


@pytest.mark.asyncio
async def test_disabled_ibkr_restart_is_logged_once_per_outage(caplog) -> None:
    ghost = _ghost()

    with patch("src.vault.Vault.get", return_value="0"), caplog.at_level(logging.INFO):
        await ghost._trigger_ghost_reset("IBKR")
        await ghost._trigger_ghost_reset("IBKR")

    messages = [record.getMessage() for record in caplog.records]
    assert messages.count(
        "MindGhost: IBKR reset suppressed because IBKR_AUTO_RESTART is disabled."
    ) == 1
    ghost.bridge.call_tool.assert_not_awaited()


def test_probe_recovery_allows_future_suppression_notice() -> None:
    ghost = _ghost()
    ghost._reset_suppressed_services.add("IBKR")

    ghost._reset_suppressed_services.discard("IBKR")

    assert "IBKR" not in ghost._reset_suppressed_services
