from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from main import TradingSystem


def _system() -> TradingSystem:
    system = TradingSystem.__new__(TradingSystem)
    system.background_tasks = {}
    return system


def test_startup_status_probes_contain_broker_failures() -> None:
    class BrokenIBKR:
        def isConnected(self) -> bool:
            raise RuntimeError("socket closed")

    class BrokenMT5:
        def terminal_info(self):
            raise RuntimeError("terminal unavailable")

    system = _system()
    system.ibkr_client = BrokenIBKR()
    system.mt5_client = BrokenMT5()

    assert system._get_status_icon("ibkr") == "RED ERROR"
    assert system._get_status_icon("mt5") == "RED ERROR"


def test_startup_status_reports_probing_and_online_states() -> None:
    system = _system()
    system.background_tasks = {"connect_ibkr": object(), "connect_mt5": object()}
    system.ibkr_client = None
    system.mt5_client = None
    system.qdb = SimpleNamespace(is_active=True)
    system.dhatu_oracle = object()

    assert system._get_status_icon("ibkr") == "YELLOW PROBING"
    assert system._get_status_icon("mt5") == "YELLOW PROBING"
    assert system._get_status_icon("qdb") == "GREEN ACTIVE"
    assert system._get_status_icon("dhatu") == "GREEN CALIBRATED"


def test_startup_status_preserves_openbb_fallback_detail() -> None:
    system = _system()
    system._openbb_provider = SimpleNamespace(
        health_status=lambda: (
            "FALLBACK",
            "OpenBB SDK unavailable; pipeline fallback provider=yfinance",
        )
    )

    status = system._get_openbb_startup_status()

    assert status == (
        "YELLOW FALLBACK - OpenBB SDK unavailable; pipeline fallback provider=yfinance"
    )


def test_realtime_watchlist_matches_scanner_execution_watchlist() -> None:
    from brain_data import DataProvider

    assert TradingSystem.execution_watchlist() == list(DataProvider.EXECUTION_WATCHLIST)
    assert len(TradingSystem.execution_watchlist()) == 26


@pytest.mark.asyncio
async def test_ibkr_runtime_rebind_updates_dms_brain_and_reconciles() -> None:
    system = _system()
    client = object()
    conn = SimpleNamespace(
        ib=None,
        is_reconnecting=True,
        _callbacks_registered=True,
        ensure_connection=AsyncMock(),
    )
    brain = SimpleNamespace(
        ibkr_client=None,
        ibkr_conn=conn,
        _reconcile_broker_positions=AsyncMock(),
    )
    dms = SimpleNamespace(ibkr_client=None)
    system.ibkr_client = client
    system.trading_brain = brain
    system.dms = dms

    await system._bind_ibkr_runtime()

    assert dms.ibkr_client is client
    assert brain.ibkr_client is client
    assert conn.ib is client
    assert conn.is_reconnecting is False
    assert conn._callbacks_registered is False
    conn.ensure_connection.assert_awaited_once()
    brain._reconcile_broker_positions.assert_awaited_once()


@pytest.mark.asyncio
async def test_questdb_init_uses_detected_config_when_vault_toggle_empty() -> None:
    system = _system()
    system.bus = object()
    system.profiler = SimpleNamespace(mark=lambda _name: None)

    adapter = SimpleNamespace(enabled=True, start=AsyncMock(), is_active=True)
    candle_writer = SimpleNamespace(start=AsyncMock())

    def vault_get(key: str, default=None):
        values = {
            "QUESTDB_ENABLED": "",
            "QUESTDB_HOST": default,
            "QUESTDB_PORT": default,
            "QUESTDB_PG_PORT": default,
            "QUESTDB_USER": default,
            "QUESTDB_PASSWORD": default,
            "QUESTDB_CONNECT_TIMEOUT_SEC": default,
        }
        return values.get(key, default)

    with (
        patch("main.QUESTDB_ENABLED", True),
        patch("main.Vault.get", side_effect=vault_get),
        patch("main.QuestDBAdapter", return_value=adapter) as adapter_cls,
        patch("questdb_candle_writer.CandleWriter", return_value=candle_writer),
    ):
        await system._init_questdb()

    assert adapter_cls.call_args.kwargs["enabled"] is True
    adapter.start.assert_awaited_once()
    candle_writer.start.assert_awaited_once_with(system.bus)


@pytest.mark.asyncio
async def test_ibkr_reconnect_loop_recovers_offline_execution() -> None:
    class OfflineClient:
        def isConnected(self) -> bool:
            return False

    system = _system()
    system.ibkr_client = OfflineClient()
    system.is_running = True
    system._shutdown_in_progress = False
    system._ibkr_outage_active = False
    system.connect_ibkr = AsyncMock(return_value=True)
    system._bind_ibkr_runtime = AsyncMock()
    system.send_telegram_notification = AsyncMock(return_value=True)
    system._persist_runtime_health_snapshot = AsyncMock()

    async def stop_after_recovery(_delay: float) -> None:
        system.is_running = False

    with patch("main.asyncio.sleep", side_effect=stop_after_recovery):
        await system._run_ibkr_reconnect_loop()

    system.connect_ibkr.assert_awaited_once()
    system._bind_ibkr_runtime.assert_awaited_once()
    assert system._ibkr_outage_active is False
    assert system.send_telegram_notification.await_count == 2


@pytest.mark.asyncio
async def test_ibkr_reconnect_loop_uses_critical_delay_when_positions_exposed() -> None:
    class OfflineClient:
        def isConnected(self) -> bool:
            return False

    system = _system()
    system.ibkr_client = OfflineClient()
    system.trading_brain = SimpleNamespace(
        positions=[SimpleNamespace(account_type="ibkr", qty=10)]
    )
    system.is_running = True
    system._shutdown_in_progress = False
    system._ibkr_outage_active = False
    system.connect_ibkr = AsyncMock(return_value=False)
    system.send_telegram_notification = AsyncMock(return_value=True)
    system._persist_runtime_health_snapshot = AsyncMock()

    sleep_calls: list[float] = []

    async def stop_after_retry(delay: float) -> None:
        sleep_calls.append(delay)
        system.is_running = False

    with (
        patch.dict(
            "main.os.environ",
            {
                "SOVEREIGN_IBKR_RECONNECT_INTERVAL_SEC": "15",
                "SOVEREIGN_IBKR_RECONNECT_MAX_INTERVAL_SEC": "300",
                "SOVEREIGN_IBKR_RECONNECT_CRITICAL_INTERVAL_SEC": "7",
            },
        ),
        patch("main.asyncio.sleep", side_effect=stop_after_retry),
    ):
        await system._run_ibkr_reconnect_loop()

    assert sleep_calls == [7.0]
    system.connect_ibkr.assert_awaited_once()
