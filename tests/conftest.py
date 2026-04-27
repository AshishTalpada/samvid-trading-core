from unittest.mock import AsyncMock, MagicMock  # pyre-ignore[21]

import pandas as pd  # pyre-ignore[21]
import pytest  # pyre-ignore[21]
import sys
import os
from pathlib import Path

# -- SETO V15.0: Cognitive Path Alignment --
# Ensure 'src' is in sys.path so tests can import modules directly
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
if str(_root) not in sys.path:
    sys.path.append(str(_root))


@pytest.fixture
def mock_db_conn():
    """Mock SQLite connection"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    # Mock row returns
    cursor.fetchone.return_value = (0.0,)  # Default PNL / VIX
    cursor.fetchall.return_value = []
    return conn


@pytest.fixture
def ticker():
    """Default trading symbol for tests (GAP-225 Hardening)"""
    return "SPY"


@pytest.fixture
def mock_questdb():
    """Mock QuestDBAdapter"""
    from questdb_adapter import QuestDBAdapter  # pyre-ignore[21]

    qdb = AsyncMock(spec=QuestDBAdapter)
    qdb.enabled = True

    # Mock OHLCV DataFrame return
    async def _mock_fetch(symbol, timeframe, limit=200):
        dates = pd.date_range(end=pd.Timestamp.now(), periods=20, freq="1min")
        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": [100.0] * 20,
                "high": [105.0] * 20,
                "low": [95.0] * 20,
                "close": [102.0] * 20,
                "volume": [1000] * 20,
            }
        )
        return df

    qdb.fetch_ohlcv_pandas.side_effect = _mock_fetch
    return qdb


@pytest.fixture
def sample_ohlcv_df():
    """Returns a basic 20-bar Pandas DataFrame for pattern testing"""
    dates = pd.date_range(end=pd.Timestamp.now(), periods=20, freq="1min")
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": [100.0] * 20,
            "high": [105.0] * 20,
            "low": [95.0] * 20,
            "close": [102.0] * 20,
            "volume": [1000] * 20,
        }
    )
    return df
