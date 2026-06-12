import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from main import SovereignFormatter, TradingSystem


def _system() -> TradingSystem:
    system = TradingSystem.__new__(TradingSystem)
    system.background_tasks = {}
    return system


def test_formatter_does_not_redact_short_secret_inside_normal_word() -> None:
    formatter = SovereignFormatter("%(message)s", secrets=["quest"])
    record = logging.LogRecord("test", logging.INFO, "", 0, "request accepted", (), None)

    assert formatter.format(record) == "request accepted"


def test_formatter_redacts_short_secret_as_standalone_value() -> None:
    formatter = SovereignFormatter("%(message)s", secrets=["quest"])
    record = logging.LogRecord("test", logging.INFO, "", 0, "password=quest", (), None)

    assert formatter.format(record) == "password=[REDACTED]"


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


def test_pytest_routes_main_logs_away_from_operator_log() -> None:
    expected = os.path.abspath(os.environ["SOVEREIGN_LOG_FILE"])
    assert expected.endswith("tmp\\pytest_trading_system.log") or expected.endswith(
        "tmp/pytest_trading_system.log"
    )

    file_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler, RotatingFileHandler)
    ]
    assert any(os.path.abspath(handler.baseFilename) == expected for handler in file_handlers)
    assert all(
        not os.path.abspath(handler.baseFilename).endswith(os.path.join("logs", "trading_system.log"))
        for handler in file_handlers
    )


def test_realtime_watchlist_matches_scanner_execution_watchlist() -> None:
    from brain_data import DataProvider

    assert TradingSystem.execution_watchlist() == list(DataProvider.EXECUTION_WATCHLIST)
    assert len(TradingSystem.execution_watchlist()) == 26


def test_ibkr_probe_policy_is_bounded_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SOVEREIGN_IBKR_PROBE_HOSTS", raising=False)
    monkeypatch.delenv("SOVEREIGN_IBKR_PROBE_PORTS", raising=False)
    monkeypatch.delenv("SOVEREIGN_IBKR_CLIENT_ID_ATTEMPTS", raising=False)
    monkeypatch.delenv("SOVEREIGN_IBKR_PROBE_BUDGET_SEC", raising=False)
    monkeypatch.delenv("SOVEREIGN_IBKR_PROBE_TIMEOUT_SEC", raising=False)

    system = _system()
    system.ibkr_port = 7497

    assert system._ibkr_probe_hosts() == ["127.0.0.1"]
    assert system._ibkr_probe_ports() == [7497, 4002]
    assert system._ibkr_probe_client_id_attempts() == 4
    assert system._ibkr_probe_budget_sec() == 45.0
    assert system._ibkr_probe_timeout_sec() == 3.0


def test_ibkr_probe_policy_accepts_operator_overrides(monkeypatch) -> None:
    monkeypatch.setenv("SOVEREIGN_IBKR_PROBE_HOSTS", "127.0.0.1,localhost")
    monkeypatch.setenv("SOVEREIGN_IBKR_PROBE_PORTS", "7497,4002,7497,bad")
    monkeypatch.setenv("SOVEREIGN_IBKR_CLIENT_ID_ATTEMPTS", "99")
    monkeypatch.setenv("SOVEREIGN_IBKR_PROBE_BUDGET_SEC", "2")
    monkeypatch.setenv("SOVEREIGN_IBKR_PROBE_TIMEOUT_SEC", "0.1")

    system = _system()
    system.ibkr_port = 7497

    assert system._ibkr_probe_hosts() == ["127.0.0.1", "localhost"]
    assert system._ibkr_probe_ports() == [7497, 4002]
    assert system._ibkr_probe_client_id_attempts() == 20
    assert system._ibkr_probe_budget_sec() == 5.0
    assert system._ibkr_probe_timeout_sec() == 1.0


def test_ibkr_probe_diagnostic_text_includes_socket_context(monkeypatch) -> None:
    monkeypatch.setenv("SOVEREIGN_IBKR_PROBE_HOSTS", "127.0.0.1")
    monkeypatch.setenv("SOVEREIGN_IBKR_PROBE_PORTS", "7497")

    system = _system()
    system.ibkr_port = 7497
    system.ibkr_client_id = 500
    system._ibkr_last_probe_summary = {
        "hosts": ["127.0.0.1"],
        "ports": [7497],
        "client_id_start": 500,
        "client_id_attempts": 2,
        "last_error": "TimeoutError",
    }

    text = system._ibkr_probe_diagnostic_text(software_active=True)

    assert "IBKR app=running" in text
    assert "hosts=127.0.0.1" in text
    assert "ports=7497" in text
    assert "clientIds=500-501" in text
    assert "TimeoutError" in text


def test_ibkr_operator_action_explains_paper_disclaimer() -> None:
    system = _system()
    system._ibkr_last_probe_summary = {
        "last_error": "127.0.0.1:7497 clientId=500: IBKR 10141: disclaimer required",
        "operator_action_required": True,
    }

    message = system._ibkr_operator_action_message()

    assert message is not None
    assert message.startswith("[EXECUTION] ACTION REQUIRED:")
    assert "accept the paper-trading API disclaimer" in message
    assert "reconnect automatically" in message


def test_ibkr_operator_action_ignores_generic_timeout() -> None:
    system = _system()
    system._ibkr_last_probe_summary = {
        "last_error": "127.0.0.1:7497 clientId=500: TimeoutError",
        "operator_action_required": False,
    }

    assert system._ibkr_operator_action_message() is None


def test_ibkr_operator_gate_logging_is_throttled() -> None:
    system = _system()

    assert system._ibkr_operator_gate_log_due("IBKR 10141", now=100.0) is True
    assert system._ibkr_operator_gate_log_due("IBKR 10141", now=200.0) is False
    assert system._ibkr_operator_gate_log_due("IBKR 10141", now=1000.0) is True
    assert system._ibkr_operator_gate_log_due("IBKR 99999", now=1001.0) is True


@pytest.mark.asyncio
async def test_aegis_periodically_revalidates_external_watchdog() -> None:
    system = _system()
    system.is_running = True
    system._shutdown_in_progress = False
    system._shutdown_event = SimpleNamespace(is_set=lambda: False)
    system._last_tick_time = 0.0
    system._should_alert_hft_starvation = lambda _drift: False
    system.mt5_client = None

    async def verify_once() -> None:
        system.is_running = False

    system._verify_watchdog = AsyncMock(side_effect=verify_once)

    with patch("main.asyncio.sleep", new=AsyncMock(return_value=None)):
        await system._run_aegis_watchdog()

    system._verify_watchdog.assert_awaited_once()


def test_write_pid_reclaims_dead_stale_lock(tmp_path, monkeypatch) -> None:
    import psutil

    system = _system()
    monkeypatch.delenv("SOVEREIGN_SKIP_PID_CHECK", raising=False)
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pid_file = data_dir / "main.pid"
    pid_file.write_text("999999", encoding="utf-8")
    monkeypatch.setattr(psutil, "pid_exists", lambda _pid: False)

    system._write_pid()

    assert pid_file.read_text(encoding="utf-8") == str(os.getpid())


def test_shutdown_request_accepts_current_pid(tmp_path, monkeypatch) -> None:
    system = _system()
    request_path = tmp_path / "shutdown.request"
    request_path.write_text(str(os.getpid()), encoding="utf-8")
    system._shutdown_request_path = request_path

    assert system._consume_shutdown_request() is True
    assert not request_path.exists()


def test_shutdown_request_discards_stale_pid(tmp_path, caplog) -> None:
    system = _system()
    request_path = tmp_path / "shutdown.request"
    request_path.write_text(str(os.getpid() + 1), encoding="utf-8")
    system._shutdown_request_path = request_path

    with caplog.at_level(logging.WARNING):
        assert system._consume_shutdown_request() is False

    assert not request_path.exists()
    assert "Discarded stale shutdown request" in caplog.text


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
async def test_run_forever_exits_immediately_when_shutdown_requested() -> None:
    system = _system()
    system._shutdown_event = asyncio.Event()
    system._shutdown_event.set()
    system._persist_runtime_health_snapshot = AsyncMock()

    await system._run_forever()

    system._persist_runtime_health_snapshot.assert_awaited_once()


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
