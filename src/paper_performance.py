"""Cost-aware performance evidence from closed SQLite paper trades."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BASELINE_STATE_KEY = "paper_performance_baseline"


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


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.isdigit():
            number = int(raw)
            if number > 10_000_000_000_000_000:
                return datetime.fromtimestamp(number / 1_000_000_000, tz=timezone.utc)
            return datetime.fromtimestamp(number, tz=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.OperationalError:
        return set()


def load_performance_baseline(db_path: str | Path = "data/trading.db") -> dict[str, Any] | None:
    """Load the persisted post-repair measurement boundary, if one exists."""
    with sqlite3.connect(str(db_path), timeout=60.0) as conn:
        try:
            row = conn.execute(
                "SELECT value FROM system_state WHERE key=?",
                (BASELINE_STATE_KEY,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    if not row:
        return None
    payload = json.loads(row[0])
    min_trade_id = int(payload["min_trade_id"])
    if min_trade_id < 1:
        raise ValueError("paper performance baseline min_trade_id must be positive")
    return {**payload, "min_trade_id": min_trade_id}


def establish_performance_baseline(
    db_path: str | Path = "data/trading.db",
    *,
    reason: str,
    force: bool = False,
) -> dict[str, Any]:
    """Persist the next trade ID as a clean evidence boundary."""
    if not reason.strip():
        raise ValueError("paper performance baseline requires a reason")
    with sqlite3.connect(str(db_path), timeout=60.0) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing = conn.execute(
            "SELECT value FROM system_state WHERE key=?",
            (BASELINE_STATE_KEY,),
        ).fetchone()
        if existing and not force:
            raise ValueError("paper performance baseline already exists; use force=True to replace it")
        max_trade_id = int(conn.execute("SELECT COALESCE(MAX(id), 0) FROM trades").fetchone()[0])
        payload = {
            "min_trade_id": max_trade_id + 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason.strip(),
        }
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (BASELINE_STATE_KEY, json.dumps(payload, sort_keys=True), payload["created_at"]),
        )
        conn.commit()
    return payload


def build_paper_performance(
    db_path: str | Path = "data/trading.db",
    *,
    starting_equity: float = 100_000.0,
    trading_modes: tuple[str, ...] = ("paper", "ibkr_paper"),
    min_trade_id: int | None = None,
) -> dict[str, Any]:
    """Return net performance evidence from genuine closed paper trades."""
    baseline = load_performance_baseline(db_path) if min_trade_id is None else None
    resolved_min_trade_id = int(baseline["min_trade_id"]) if baseline else int(min_trade_id or 0)
    placeholders = ",".join("?" for _ in trading_modes)
    with sqlite3.connect(str(db_path), timeout=60.0) as conn:
        columns = _table_columns(conn, "trades")
        timestamp_select = "timestamp" if "timestamp" in columns else "NULL"
        query = f"""
            SELECT
                id, {timestamp_select}, trading_mode, outcome, COALESCE(pnl_dollars, 0),
                COALESCE(net_pnl, pnl_dollars, 0), COALESCE(commission, 0),
                COALESCE(slippage, 0), COALESCE(r_multiple, 0)
            FROM trades
            WHERE outcome IN ('WIN', 'LOSS', 'BREAKEVEN')
              AND trading_mode IN ({placeholders})
              AND id >= ?
            ORDER BY id ASC
        """
        rows = conn.execute(query, (*trading_modes, resolved_min_trade_id)).fetchall()

    pnls = [value for row in rows if (value := _as_float(row[5])) is not None]
    gross_pnls = [value for row in rows if (value := _as_float(row[4])) is not None]
    commissions = [value for row in rows if (value := _as_float(row[6])) is not None]
    slippages = [value for row in rows if (value := _as_float(row[7])) is not None]
    r_multiples = [value for row in rows if (value := _as_float(row[8])) is not None]
    timestamps = [value for row in rows if (value := _parse_timestamp(row[1])) is not None]
    first_ts = min(timestamps) if timestamps else None
    last_ts = max(timestamps) if timestamps else None
    calendar_days = (
        (last_ts - first_ts).total_seconds() / 86_400.0 if first_ts and last_ts else 0.0
    )
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    trade_count = len(pnls)

    return {
        "source": "sqlite_closed_paper_trades",
        "trading_modes": list(trading_modes),
        "window": {
            "min_trade_id": resolved_min_trade_id,
            "first_trade_id": int(rows[0][0]) if rows else None,
            "last_trade_id": int(rows[-1][0]) if rows else None,
            "first_trade_timestamp": first_ts.isoformat() if first_ts else None,
            "last_trade_timestamp": last_ts.isoformat() if last_ts else None,
            "calendar_days": round(calendar_days, 4),
            "timestamp_samples": len(timestamps),
            "baseline_source": "stored_system_state" if baseline else "explicit_or_full_history",
            "baseline": baseline,
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
