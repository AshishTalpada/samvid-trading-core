import os
import sys
import traceback


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
