import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ShadowTrade:
    symbol: str
    entry_price: float
    side: str  # "BUY" | "SELL"
    timestamp: datetime
    pnl: float = 0.0
    is_closed: bool = False


class GhostShadowSim:
    """
    Forks live ticks into a virtual PnL tracker.
    Used to measure signal quality without risking capital.
    """

    def __init__(self):
        self.active_trades: Dict[str, ShadowTrade] = {}
        self.history: List[ShadowTrade] = []
        self.total_shadow_pnl = 0.0

    def fork_signal(self, symbol: str, price: float, side: str):
        """Creates a shadow trade for a signal."""
        if symbol in self.active_trades:
            return  # Already tracking

        trade = ShadowTrade(symbol=symbol, entry_price=price, side=side, timestamp=datetime.now())
        self.active_trades[symbol] = trade
        logger.info(f" SHADOW-SIM: Opened {side} for {symbol} at ${price:.2f}")

    def update(self, symbol: str, current_price: float):
        """Updates the PnL of active shadow trades based on live ticks."""
        if symbol not in self.active_trades:
            return

        trade = self.active_trades[symbol]
        if trade.side == "BUY":
            trade.pnl = (current_price - trade.entry_price) / trade.entry_price
        else:
            trade.pnl = (trade.entry_price - current_price) / trade.entry_price

        # Auto-close if profit/loss hits target (placeholder logic)
        if trade.pnl > 0.02 or trade.pnl < -0.01:
            self.close_shadow_trade(symbol, current_price)

    def close_shadow_trade(self, symbol: str, exit_price: float):
        if symbol not in self.active_trades:
            return

        trade = self.active_trades.pop(symbol)
        trade.is_closed = True
        self.total_shadow_pnl += trade.pnl
        self.history.append(trade)
        logger.info(f" SHADOW-SIM: Closed {symbol} at ${exit_price:.2f} | PnL: {trade.pnl:.2%}")

    def get_stats(self):
        wins = sum(1 for t in self.history if t.pnl > 0)
        losses = sum(1 for t in self.history if t.pnl <= 0)
        win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0
        return {
            "total_pnl": self.total_shadow_pnl,
            "win_rate": win_rate,
            "active_count": len(self.active_trades),
        }
