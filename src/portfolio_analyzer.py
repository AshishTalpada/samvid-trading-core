"""
src/portfolio_analyzer.py — Live Session Portfolio Performance Tracker
Sovereign session performance tracker — live stats, no approximations.

Records every closed trade and computes live stats:
  - Total P&L (USD + %)
  - Live Sharpe ratio
  - Max drawdown
  - Win rate, profit factor
  - Per-symbol breakdown

Wire-in:
  - brain.py: call ANALYZER.record_close() when a position exits
  - api_server.py: expose ANALYZER.summary() as a live dashboard endpoint
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger("PortfolioAnalyzer")


@dataclass
class ClosedTrade:
    symbol: str
    side: str  # "LONG" | "SHORT"
    quantity: float
    entry_price: float
    exit_price: float
    pnl_usd: float
    pnl_pct: float
    commission: float
    ts_entry: datetime
    ts_exit: datetime
    task_id: Optional[str] = None

    @property
    def duration_minutes(self) -> float:
        return (self.ts_exit - self.ts_entry).total_seconds() / 60.0


class LivePortfolioAnalyzer:
    """
    Real-time performance tracker for a live trading session.
    Maintains full trade history and recomputes all stats incrementally.
    """

    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        self._trades: list[ClosedTrade] = []
        self._equity_curve: list[float] = [starting_capital]
        self._by_symbol: dict[str, list[ClosedTrade]] = defaultdict(list)
        self._session_start: datetime = datetime.now(timezone.utc)

    # ------------------------------------------------------------------ recording

    def record_close(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        pnl_usd: float,
        commission: float = 1.0,
        ts_entry: Optional[datetime] = None,
        ts_exit: Optional[datetime] = None,
        task_id: Optional[str] = None,
    ) -> None:
        """Record a completed trade. Call this every time a position is closed."""
        now = datetime.now(timezone.utc)
        entry_ts = ts_entry or now
        exit_ts = ts_exit or now

        # Compute pnl_pct from prices
        if entry_price > 0:
            direction = 1.0 if side == "LONG" else -1.0
            pnl_pct = direction * (exit_price - entry_price) / entry_price
        else:
            pnl_pct = 0.0

        trade = ClosedTrade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            commission=commission,
            ts_entry=entry_ts,
            ts_exit=exit_ts,
            task_id=task_id,
        )
        self._trades.append(trade)
        self._by_symbol[symbol].append(trade)
        self._equity_curve.append(self._equity_curve[-1] + pnl_usd)

        logger.info(
            f"Portfolio: [{symbol}] closed | P&L ${pnl_usd:+.2f} ({pnl_pct:+.2%}) | "
            f"Running: ${self.total_pnl_usd:+.2f} | Sharpe: {self.live_sharpe:.2f}"
        )

    # ------------------------------------------------------------------ core metrics

    @property
    def n_trades(self) -> int:
        return len(self._trades)

    @property
    def total_pnl_usd(self) -> float:
        return sum(t.pnl_usd for t in self._trades)

    @property
    def total_pnl_pct(self) -> float:
        return self.total_pnl_usd / max(self.starting_capital, 1e-10)

    @property
    def win_rate(self) -> float:
        if not self._trades:
            return 0.0
        return sum(1 for t in self._trades if t.pnl_usd > 0) / len(self._trades)

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl_usd for t in self._trades if t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in self._trades if t.pnl_usd <= 0))
        return gross_win / max(gross_loss, 1e-10)

    @property
    def avg_win_usd(self) -> float:
        wins = [t.pnl_usd for t in self._trades if t.pnl_usd > 0]
        return float(np.mean(wins)) if wins else 0.0

    @property
    def avg_loss_usd(self) -> float:
        losses = [abs(t.pnl_usd) for t in self._trades if t.pnl_usd <= 0]
        return float(np.mean(losses)) if losses else 0.0

    @property
    def live_sharpe(self) -> float:
        """Annualised Sharpe from per-trade returns (proxy for session Sharpe)."""
        if len(self._trades) < 3:
            return 0.0
        pnls = np.array([t.pnl_pct for t in self._trades])
        return float(np.mean(pnls) / (np.std(pnls) + 1e-10) * np.sqrt(252))

    @property
    def max_drawdown(self) -> float:
        eq = np.array(self._equity_curve)
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / (peak + 1e-10)
        return float(np.min(dd))

    @property
    def current_equity(self) -> float:
        return self._equity_curve[-1]

    # ------------------------------------------------------------------ symbol breakdown

    def symbol_summary(self, symbol: str) -> dict:
        trades = self._by_symbol.get(symbol, [])
        if not trades:
            return {}
        total = sum(t.pnl_usd for t in trades)
        wins = sum(1 for t in trades if t.pnl_usd > 0)
        return {
            "symbol": symbol,
            "trades": len(trades),
            "pnl_usd": round(total, 2),
            "win_rate": f"{wins / len(trades):.1%}",
        }

    # ------------------------------------------------------------------ summary

    def summary(self) -> dict:
        """Full session summary — expose on dashboard endpoint."""
        session_hours = (datetime.now(timezone.utc) - self._session_start).total_seconds() / 3600
        return {
            "session_hours": round(session_hours, 2),
            "trades": self.n_trades,
            "equity_usd": round(self.current_equity, 2),
            "pnl_usd": round(self.total_pnl_usd, 2),
            "pnl_pct": f"{self.total_pnl_pct:+.2%}",
            "win_rate": f"{self.win_rate:.1%}",
            "profit_factor": round(self.profit_factor, 3),
            "avg_win_usd": round(self.avg_win_usd, 2),
            "avg_loss_usd": round(self.avg_loss_usd, 2),
            "live_sharpe": round(self.live_sharpe, 3),
            "max_drawdown": f"{self.max_drawdown:.2%}",
        }

    def log_summary(self) -> None:
        s = self.summary()
        logger.info(
            f"📊 SESSION SUMMARY | Trades: {s['trades']} | P&L: {s['pnl_pct']} "
            f"(${s['pnl_usd']:+.2f}) | WR: {s['win_rate']} | Sharpe: {s['live_sharpe']} | "
            f"MaxDD: {s['max_drawdown']}"
        )


# Global instance for live session tracking (starting capital matches typical prop firm account or config)
try:
    import config as _cfg
    starting_capital: float = getattr(_cfg, "ACCOUNT_SIZE", getattr(_cfg, "STARTING_CAPITAL_CAD", 100_000.0))
except ImportError:
    starting_capital = 100_000.0

PORTFOLIO_ANALYZER = LivePortfolioAnalyzer(starting_capital=starting_capital)
