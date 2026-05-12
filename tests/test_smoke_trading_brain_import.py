import asyncio
import importlib
import os
import sys
import traceback
from types import ModuleType
from unittest.mock import AsyncMock, patch


def test_import_trading_brain_smoke():
    """Smoke test: import `TradingBrain` from `src/brain.py`.

    This test ensures the class can be imported without requiring live infrastructure.
    It sets conservative environment flags to avoid PID checks and live-mode side effects.
    """
    os.environ.setdefault("SOVEREIGN_SKIP_PID_CHECK", "1")
    os.environ.setdefault("ALLOW_FORCE_LIVE", "0")

    # Ensure local src is on sys.path
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    try:
        from brain import TradingBrain  # type: ignore

        assert TradingBrain is not None
    except Exception:
        traceback.print_exc()
        raise


def test_trading_system_startup_smoke():
    """Smoke test: instantiate `TradingSystem` from `src/main.py`.

    This test validates the conservative startup safety path and PID bypass.
    """
    os.environ.setdefault("SOVEREIGN_SKIP_PID_CHECK", "1")
    os.environ.setdefault("ALLOW_FORCE_LIVE", "0")

    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    try:
        from main import TradingSystem  # type: ignore

        system = TradingSystem()
        assert system.mode == "paper"
    except Exception:
        traceback.print_exc()
        raise


def test_apply_runtime_safety_defaults_to_paper_when_live_not_authorized():
    """Test that startup safety forces paper mode when explicit authorization is absent."""
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from safety import apply_runtime_safety  # type: ignore

    class DummySystem:
        mode = "live"

    dummy = DummySystem()
    with patch.dict(os.environ, {"ALLOW_FORCE_LIVE": "0", "TRADING_MODE": "live"}, clear=False):
        with patch("safety.send_telegram_alert", return_value=None):
            apply_runtime_safety(dummy)
    assert dummy.mode == "paper"


def test_apply_runtime_safety_allows_live_when_authorized():
    """Test that startup safety preserves live mode when ALLOW_FORCE_LIVE=1."""
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from safety import apply_runtime_safety  # type: ignore

    class DummySystem:
        mode = "paper"

    dummy = DummySystem()
    with patch.dict(os.environ, {"ALLOW_FORCE_LIVE": "1", "TRADING_MODE": "live"}, clear=False):
        with patch("safety.send_telegram_alert", return_value=None):
            apply_runtime_safety(dummy)
    assert dummy.mode == "live"


def test_ibkr_paper_mode_requires_ibkr_connection_flag():
    """ibkr_paper mode should be recognized as requiring a real IBKR connection."""
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    with patch.dict(
        os.environ,
        {
            "ALLOW_FORCE_LIVE": "0",
            "TRADING_MODE": "ibkr_paper",
            "SOVEREIGN_SKIP_PID_CHECK": "1",
        },
        clear=False,
    ):
        importlib.invalidate_caches()
        import main  # type: ignore

        system = main.TradingSystem()
        assert system.mode == "ibkr_paper"
        assert system.requires_ibkr_connection is True


def test_paper_mode_startup_skips_ibkr_executable_check():
    """Paper mode should not require an IBKR executable to initialize."""
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    with patch.dict(os.environ, {"ALLOW_FORCE_LIVE": "0", "TRADING_MODE": "paper"}, clear=False):
        importlib.invalidate_caches()
        import main  # type: ignore

        system = main.TradingSystem()
        assert system.mode == "paper"

        with patch.object(main.MindSystem, "_tool_find_executable", AsyncMock(return_value=False)):
            with patch.object(main.TimeSync, "sync", AsyncMock(return_value=None)):
                with patch.object(main.TradingSystem, "_verify_watchdog", AsyncMock(return_value=None)):
                    with patch.object(main.TradingSystem, "_init_questdb", AsyncMock(return_value=None)):
                        with patch.object(main.TradingSystem, "_init_api_server", AsyncMock(return_value=None)):
                            with patch.object(main.TradingSystem, "_init_search_providers", AsyncMock(return_value=None)):
                                with patch.object(main.TradingSystem, "_init_hft_streamer", AsyncMock(return_value=None)):
                                    asyncio.run(system.async_init())


def test_ibkr_paper_mode_starts_ibkr_connection():
    """ibkr_paper mode should instantiate IBKR and attempt broker connect."""
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    fake_ib_module = ModuleType("ib_insync")

    class FakeIB:
        def __init__(self, *args, **kwargs):
            pass

        def isConnected(self):
            return False

    fake_ib_module.IB = FakeIB

    with patch.dict(
        os.environ,
        {
            "ALLOW_FORCE_LIVE": "0",
            "TRADING_MODE": "ibkr_paper",
            "SOVEREIGN_SKIP_PID_CHECK": "1",
        },
        clear=False,
    ):
        importlib.invalidate_caches()
        import main  # type: ignore

        with patch.dict(sys.modules, {"ib_insync": fake_ib_module}):
            system = main.TradingSystem()
            assert system.mode == "ibkr_paper"
            assert system.requires_ibkr_connection is True
            system.telegram_remote = None
            system.start_trading_brain = AsyncMock(return_value=None)
            system.start_data_pipeline = AsyncMock(return_value=None)
            system._start_background_tasks = AsyncMock(return_value=None)
            system._start_supervised_task = AsyncMock(return_value=None)
            system.send_telegram_notification = AsyncMock(return_value=None)

            with patch("risk_invariants.RiskInvariants.verify_config", return_value=True):
                with patch.object(main.TradingSystem, "check_paper", return_value=None):
                    with patch.object(main.TradingSystem, "start_dms", AsyncMock(return_value=None)):
                        with patch.object(main.TradingSystem, "connect_ibkr", AsyncMock(return_value=True)) as mock_connect:
                            with patch.object(main.TradingSystem, "connect_mt5", AsyncMock(return_value=True)):
                                asyncio.run(system.startup())
                                assert mock_connect.called
