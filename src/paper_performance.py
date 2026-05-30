"""Cost-aware performance evidence from closed SQLite paper trades."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


def _max_drawdown(pnls: Iterable[float], starting_equity: float) -> float:
    equity = float(starting_equity)
    peak = equity
    max_drawdown = 0.0
    for pnl in pnls:
        equity += float(pnl)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / max(peak, 1e-12))
    return max_drawdown


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_paper_performance(
    db_path: str | Path = "data/trading.db",
    *,
    starting_equity: float = 100_000.0,
    trading_modes: tuple[str, ...] = ("paper", "ibkr_paper"),
    min_trade_id: int = 0,
) -> dict[str, Any]:
    """Return net performance evidence from genuine closed paper trades."""
    placeholders = ",".join("?" for _ in trading_modes)
    query = f"""
        SELECT
            id, trading_mode, outcome, COALESCE(pnl_dollars, 0),
            COALESCE(net_pnl, pnl_dollars, 0), COALESCE(commission, 0),
            COALESCE(slippage, 0), COALESCE(r_multiple, 0)
        FROM trades
        WHERE outcome IN ('WIN', 'LOSS', 'BREAKEVEN')
          AND trading_mode IN ({placeholders})
          AND id >= ?
        ORDER BY id ASC
    """
    with sqlite3.connect(str(db_path), timeout=60.0) as conn:
        rows = conn.execute(query, (*trading_modes, int(min_trade_id))).fetchall()

    pnls = [value for row in rows if (value := _as_float(row[4])) is not None]
    gross_pnls = [value for row in rows if (value := _as_float(row[3])) is not None]
    commissions = [value for row in rows if (value := _as_float(row[5])) is not None]
    slippages = [value for row in rows if (value := _as_float(row[6])) is not None]
    r_multiples = [value for row in rows if (value := _as_float(row[7])) is not None]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    trade_count = len(pnls)

    return {
        "source": "sqlite_closed_paper_trades",
        "trading_modes": list(trading_modes),
        "window": {
            "min_trade_id": int(min_trade_id),
            "first_trade_id": int(rows[0][0]) if rows else None,
            "last_trade_id": int(rows[-1][0]) if rows else None,
        },
        "metrics": {
            "trades": trade_count,
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": trade_count - len(wins) - len(losses),
            "win_rate": len(wins) / trade_count if trade_count else 0.0,
            "net_pnl": sum(pnls),
            "gross_pnl": sum(gross_pnls),
            "gross_pnl_samples": len(gross_pnls),
            "expectancy_net": sum(pnls) / trade_count if trade_count else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float("inf") if wins else 0.0,
            "max_drawdown_pct": _max_drawdown(pnls, starting_equity),
            "total_commission": sum(commissions),
            "total_slippage": sum(slippages),
            "cost_drag": sum(commissions) + sum(slippages),
            "avg_r_multiple": sum(r_multiples) / len(r_multiples) if r_multiples else 0.0,
            "r_multiple_samples": len(r_multiples),
            "rows_excluded_missing_numeric_net_pnl": len(rows) - trade_count,
        },
    }
