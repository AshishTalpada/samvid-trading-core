from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import agent_c_mt5


def test_close_all_positions_uses_ticket_close_instead_of_opposite_order(monkeypatch) -> None:
    agent = agent_c_mt5.MetaTrader5Agent(
        account=123,
        password="test",
        server="paper",
        magic_number=777777,
    )
    agent.connected = True
    agent.close_position = MagicMock(return_value=True)
    agent.execute_market_order = MagicMock()
    positions = [
        SimpleNamespace(ticket=11, symbol="EURUSD", magic=777777),
        SimpleNamespace(ticket=22, symbol="GBPUSD", magic=999999),
    ]
    monkeypatch.setattr(
        agent_c_mt5,
        "_get_mt5_module",
        lambda: SimpleNamespace(positions_get=MagicMock(return_value=positions)),
    )

    agent.close_all_positions()

    agent.close_position.assert_called_once_with(11)
    agent.execute_market_order.assert_not_called()
