import json
import os
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.brain import TradingBrain
from src.dhatu_oracle import DhatuOracle

# Samvid v1.0-beta-beta-beta PERSISTENCE AUDIT (Agent S)
# Verifies that the system correctly restores its state from the database.


@pytest.mark.asyncio
async def test_dhatu_persistence_recovery() -> None:
    db_path = "data/trading.db"
    if not os.path.exists("data"):
        os.makedirs("data")

    # 1. Inject 'Abhava' (FREEZE) state into database
    state_data = {
        "dhatu_state": "Abhava",
        "action_protocol": "CASH",
        "risk_modifier": 0.0,
        "causation_summary": "AUDIT: Intentional freeze for persistence recovery check.",
        "confidence": 0.99,
        "generated_at": datetime.now().isoformat(),
    }

    previous_oracle_state = None
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)"
        )
        previous_oracle_state = conn.execute(
            "SELECT value, updated_at FROM system_state WHERE key = ?",
            ("oracle_state",),
        ).fetchone()
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            ("oracle_state", json.dumps(state_data), datetime.now()),
        )
    conn.close()

    try:
        # 2. Initializing DhatuOracle (should load from DB)
        oracle = DhatuOracle()

        current_state = oracle.get_current_state()
        assert current_state is not None
        assert current_state.dhatu_state == "Abhava"

        # 3. Initializing TradingBrain (should sync with Oracle)
        mock_db = MagicMock()
        mock_ibkr = MagicMock()
        mock_mt5 = MagicMock()

        brain = TradingBrain(
            db_conn=mock_db, ibkr_client=mock_ibkr, mt5_client=mock_mt5, dhatu_oracle=oracle
        )

        assert brain._oracle_freeze is True
        assert brain._oracle_dhatu == "Abhava"
    finally:
        with sqlite3.connect(db_path) as conn:
            if previous_oracle_state:
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
                    ("oracle_state", previous_oracle_state[0], previous_oracle_state[1]),
                )
            else:
                conn.execute("DELETE FROM system_state WHERE key = ?", ("oracle_state",))
        conn.close()


if __name__ == "__main__":
    pytest.main([__file__])
