"""Account value, P&L, and drawdown helpers extracted from brain.py.

Provides the AccountingMixin with methods for querying account equity,
daily P&L, and updating the drawdown ladders.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from config import STARTING_CAPITAL_CAD

logger = logging.getLogger(__name__)


class AccountingMixin:
    """Mixin: account value, daily P&L, drawdown updates."""

    async def _get_account_value(self, account_type: str, force_fresh: bool = False) -> float:
        """Get account equity value."""
        now = time.time()
        if not force_fresh and (now - self._last_account_value["timestamp"]) < 60.0:
            cached = self._last_account_value.get(account_type, 0.0)
            if cached > 0:
                return cached

        try:
            val = STARTING_CAPITAL_CAD
            if account_type == "ibkr" and self.ibkr_client:
                if hasattr(self.ibkr_client, "isConnected") and self.ibkr_client.isConnected():
                    # Priority: Use NetLiquidation to avoid currency confusion
                    acc_vals = self.ibkr_client.accountValues()
                    fallback_val = (
                        self.ibkr_drawdown.peak_equity
                        if hasattr(self, "ibkr_drawdown") and self.ibkr_drawdown.peak_equity > 0
                        else STARTING_CAPITAL_CAD
                    )
                    liq_vals = [float(x.value) for x in acc_vals if x.tag == "NetLiquidation"]
                    val = max(liq_vals) if liq_vals else fallback_val
            elif account_type == "mt5":
                import MetaTrader5 as mt5

                def _sync_mt5_account():
                    if not mt5.initialize():
                        return STARTING_CAPITAL_CAD
                    info = mt5.account_info()
                    return info.equity if info else STARTING_CAPITAL_CAD

                val = await asyncio.to_thread(_sync_mt5_account)

            # Update cache
            self._last_account_value[account_type] = val
            self._last_account_value["timestamp"] = now
            return val

        except Exception as e:
            logger.warning("Account check failed (non-fatal): %s", e)
            return self._last_account_value.get(account_type, STARTING_CAPITAL_CAD)

    async def _get_daily_pnl(self, account_type: str) -> float:
        """Get today's P&L: closed trades from DB + unrealized from open positions.

        The DB query runs in a thread (blocking SQLite call).  Unrealized PnL is
        computed back on the event loop so we can safely read self.positions
        and self.last_tick_prices without any cross-thread data races.
        """

        def _sync_daily_pnl() -> float:
            cursor = None
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    cursor.execute(
                        "SELECT COALESCE(SUM(pnl_dollars), 0) FROM trades "
                        "WHERE timestamp LIKE ? AND broker = ?",
                        (f"{today}%", account_type),
                    )
                    result = cursor.fetchone()
                    if result and result[0] is not None:
                        return float(result[0])
                return 0.0
            except Exception:
                return 0.0
            finally:
                if cursor is not None:
                    cursor.close()

        # Step 1 - closed PnL from DB (blocking call, must run in thread).
        closed_pnl: float = await asyncio.to_thread(_sync_daily_pnl)

        # Step 2 - unrealized PnL from open positions (event-loop safe reads).
        unrealized_pnl: float = 0.0
        for pos in list(getattr(self, "positions", [])):
            if pos.account_type != account_type:
                continue
            current_price: float = self.last_tick_prices.get(pos.symbol, 0.0)
            if current_price <= 0.0:
                # No tick price available yet - skip to avoid phantom PnL.
                continue
            qty = abs(pos.qty)
            if pos.qty > 0:
                # LONG: profit when price rises above entry.
                unrealized_pnl += (current_price - pos.entry_price) * qty
            else:
                # SHORT: profit when price falls below entry.
                unrealized_pnl += (pos.entry_price - current_price) * qty

        return closed_pnl + unrealized_pnl

    async def _update_drawdowns(self) -> None:
        """Update drawdown ladders from current account values."""
        ibkr_equity = await self._get_account_value("ibkr")
        self.ibkr_drawdown.update(ibkr_equity)
        if self.db_conn:
            cursor = None
            try:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("last_heartbeat", time.time_ns()),
                )
                # Persist peak_equity so restore_peak_equity() can read it on restart
                cursor.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("peak_equity", str(self.ibkr_drawdown.peak_equity)),
                )
                self.db_conn.commit()
            finally:
                if cursor is not None:
                    cursor.close()

        # Checkpoint every 5 minutes (throttled to avoid disk hammering)
        now_ts = int(time.time())
        if now_ts % 300 < 60:
            last_freeze = getattr(self, "_last_freeze_time", 0)
            if now_ts - last_freeze > 60:
                self._last_freeze_time = now_ts
                state_to_freeze = {
                    "positions": self.positions,
                    "peak_equity": self.ibkr_drawdown.peak_equity,
                    "win_rates": self._learned_win_rates,
                    "session_stats": self.session_stats,
                }
                _freeze_task = asyncio.create_task(
                    asyncio.to_thread(self.session_restorer.freeze_state, state_to_freeze)
                )
                self._background_tasks.add(_freeze_task)
                _freeze_task.add_done_callback(self._background_tasks.discard)

        mt5_equity = await self._get_account_value("mt5")
        self.prop_drawdown.update(mt5_equity)
