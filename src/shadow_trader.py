from typing import Dict, List


class ShadowTrader:
    """Runs recursive self-play by trading against historical ghost versions of the agent."""
    def __init__(self, history_depth: int = 50):
        self.history_depth = history_depth
        self.ghost_trades: List[Dict] = []

    def record_trade(self, signal: str, entry: float, exit_price: float) -> None:
        pnl = (exit_price - entry) / entry if signal == "BUY" else (entry - exit_price) / entry
        self.ghost_trades.append({"signal": signal, "pnl": pnl})
        if len(self.ghost_trades) > self.history_depth:
            self.ghost_trades = self.ghost_trades[-self.history_depth:]

    def get_ghost_win_rate(self) -> float:
        if not self.ghost_trades:
            return 0.5
        return sum(1 for t in self.ghost_trades if t["pnl"] > 0) / len(self.ghost_trades)

    def should_fade_signal(self) -> bool:
        return self.get_ghost_win_rate() < 0.4
