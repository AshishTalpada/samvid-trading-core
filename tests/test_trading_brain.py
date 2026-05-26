# pyright: reportMissingImports=false
from unittest.mock import AsyncMock, MagicMock, patch  # type: ignore

import pandas as pd  # pyre-ignore[21]
import pytest  # pyre-ignore[21]

try:
    from src.brain import DrawdownLevel, TradingBrain, TradingState  # type: ignore
except ImportError:
    from brain import DrawdownLevel, TradingBrain, TradingState  # type: ignore


@pytest.fixture
def brain(mock_db_conn):
    """Create a TradingBrain with mocked external dependencies."""
    with (
        patch("sqlite3.connect") as mock_connect,
        patch("src.brain.QuestDBAdapter") as mock_qdb_class,
    ):  # pyre-ignore[21]
        mock_connect.return_value = mock_db_conn
        mock_qdb_instance = mock_qdb_class.return_value
        mock_qdb_instance.start = AsyncMock()
        mock_qdb_instance.stop = AsyncMock()
        mock_qdb_instance.fetch_ohlcv_pandas = AsyncMock(return_value=pd.DataFrame())

        # Mock IBKR and MT5 clients
        mock_ibkr = MagicMock()
        mock_mt5 = MagicMock()

        tb = TradingBrain(
            db_conn=mock_db_conn, ibkr_client=mock_ibkr, mt5_client=mock_mt5, mode="paper"
        )

        # Disable the infinite loop so we can test discrete states
        tb.is_running = False

        import asyncio

        tb._get_vix = AsyncMock(return_value=15.0)  # pyre-ignore[21]
        tb._detect_regime = AsyncMock(return_value="BULL")  # pyre-ignore[21]
        tb._update_drawdowns = AsyncMock()  # pyre-ignore[21]

        yield tb

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(tb.stop())
            else:
                loop.run_until_complete(tb.stop())
        except RuntimeError:
            pass


@pytest.mark.asyncio
async def test_standby_to_scanning_transition(brain) -> None:
    """Test that a healthy TradingBrain generates a budget and moves to SCANNING."""

    # Assert initial state
    assert brain.state == TradingState.STANDBY
    assert brain.current_regime == "UNKNOWN"

    # Ensure health checks pass
    brain.ibkr_drawdown.level = DrawdownLevel.NORMAL
    brain.loss_tracker.consecutive_losses = 0

    # Run a single frame of the standby state logic
    await brain._state_standby()

    # Verify State Machine advances correctly
    assert brain.state == TradingState.SCANNING
    assert brain.current_regime == "BULL"

    # Verify Morning Budget was generated
    budget = brain.morning_budget
    assert budget.generated_at is not None
    assert budget.regime == "BULL"
    assert budget.max_trades == 20
    assert budget.min_catalyst == 55  # Samvid v1.0-beta-beta-beta Aggressive Bull Bias
    assert budget.max_risk_per_trade_pct == 0.02
