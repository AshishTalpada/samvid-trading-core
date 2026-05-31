from types import SimpleNamespace

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
