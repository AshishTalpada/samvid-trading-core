import sys
import os
sys.path.append(os.getcwd())

import unittest.mock
from unittest.mock import MagicMock, AsyncMock

# Mock sqlite3 connect before importing brain
with unittest.mock.patch('sqlite3.connect'):
    from src.brain import TradingBrain # type: ignore
    print("Successfully imported TradingBrain")
    
    # Try to instantiate with mocked QuestDB
    with unittest.mock.patch('src.brain.QuestDBAdapter') as mock_qdb:
        brain = TradingBrain(db_path=":memory:")
        print("Successfully instantiated TradingBrain with mocked QuestDB")
