"""Account value, P&L, and drawdown helpers extracted from brain.py.

Provides the AccountingMixin with methods for querying account equity,
daily P&L, and updating the drawdown ladders.
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AccountingMixin:
    """Mixin: account value, daily P&L, drawdown updates."""

    def _record_account_value(
        self,
        account_type: str,
        value: float,
        *,
        source: str,
        authoritative: bool,
        observed_at: float,
    ) -> float:
        """Store an account observation together with its provenance."""
        if not hasattr(self, "_account_value_meta"):
            self._account_value_meta = {}
        self._last_account_value[account_type] = value
        self._last_account_value[f"{account_type}_timestamp"] = observed_at
        self._last_account_value["timestamp"] = observed_at
        self._account_value_meta[account_type] = {
            "source": source,
            "authoritative": authoritative,
            "observed_at": observed_at,
        }
        return value

    def _account_value_metadata(self, account_type: str) -> dict[str, object]:
        """Return provenance for the most recent account observation."""
        metadata = getattr(self, "_account_value_meta", {}).get(account_type, {})
        return {
            "source": metadata.get("source", "unavailable"),
            "authoritative": bool(metadata.get("authoritative", False)),
            "observed_at": float(metadata.get("observed_at", 0.0) or 0.0),
        }

    @staticmethod
    def _positive_finite(value: object) -> float | None:
        """Parse a broker numeric field without letting one malformed row poison the batch."""
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if math.isfinite(parsed) and parsed > 0 else None

    async def _get_account_value(self, account_type: str, force_fresh: bool = False) -> float:
        """Get account equity without presenting configured fallbacks as broker truth."""
        now = time.time()
        cache_timestamp = float(
            self._last_account_value.get(
                f"{account_type}_timestamp", self._last_account_value.get("timestamp", 0.0)
            )
            or 0.0
        )
        if not force_fresh and (now - cache_timestamp) < 60.0:
            cached = self._last_account_value.get(account_type, 0.0)
            if math.isfinite(float(cached)) and cached > 0:
                return cached

        try:
            if account_type == "ibkr" and self.ibkr_client:
                if hasattr(self.ibkr_client, "isConnected") and self.ibkr_client.isConnected():
                    acc_vals = self.ibkr_client.accountValues()
                    net_liquidation = [x for x in acc_vals if x.tag == "NetLiquidation"]
                    base_values = [x for x in net_liquidation if x.currency == "BASE"]
                    candidates = base_values or net_liquidation
                    liquidations = [
                        parsed
                        for x in candidates
                        if (parsed := self._positive_finite(x.value)) is not None
                    ]
                    if liquidations:
                        return self._record_account_value(
                            account_type,
                            max(liquidations),
                            source="ibkr_net_liquidation",
                            authoritative=True,
                            observed_at=now,
                        )
                    logger.warning(
                        "IBKR account is connected but NetLiquidation is unavailable; "
                        "blocking fresh equity-dependent decisions."
                    )
                return self._record_account_value(
                    account_type,
                    0.0,
                    source="ibkr_unavailable",
                    authoritative=False,
                    observed_at=now,
                )
            elif account_type == "mt5":
                import MetaTrader5 as mt5

                def _sync_mt5_account():
                    if not mt5.initialize():
                        return 0.0
                    info = mt5.account_info()
                    return float(info.equity) if info else 0.0

                value = await asyncio.to_thread(_sync_mt5_account)
                authoritative = math.isfinite(value) and value > 0
                return self._record_account_value(
                    account_type,
                    value if authoritative else 0.0,
                    source="mt5_account_equity" if authoritative else "mt5_unavailable",
                    authoritative=authoritative,
                    observed_at=now,
                )

            return self._record_account_value(
                account_type,
                0.0,
                source=f"{account_type}_unavailable",
                authoritative=False,
                observed_at=now,
            )

        except Exception as e:
            logger.warning("Account check failed (non-fatal): %s", e)
            return self._record_account_value(
                account_type,
                0.0,
                source=f"{account_type}_error",
                authoritative=False,
                observed_at=now,
            )

    async def _get_realized_daily_pnl(self, account_type: str) -> float:
        """Return today's closed, cost-aware PnL for one broker."""

        def _sync_realized_daily_pnl() -> float:
            cursor = None
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    cursor.execute(
                        "SELECT COALESCE(SUM("
                        "CASE WHEN net_pnl IS NOT NULL AND "
                        "(net_pnl != 0 OR COALESCE(pnl_dollars, 0) = 0) "
                        "THEN net_pnl ELSE COALESCE(pnl_dollars, 0) END), 0) "
                        "FROM trades WHERE timestamp LIKE ? AND LOWER(broker) = LOWER(?) "
                        "AND outcome IN ('WIN', 'LOSS', 'BREAKEVEN')",
                        (f"{today}%", account_type),
                    )
                    result = cursor.fetchone()
                    if result and result[0] is not None:
                        value = float(result[0])
                        return value if math.isfinite(value) else 0.0
                return 0.0
            except Exception as exc:
                logger.warning("Realized daily PnL query failed: %s", exc)
                return 0.0
            finally:
                if cursor is not None:
                    cursor.close()

        return await asyncio.to_thread(_sync_realized_daily_pnl)

    async def _get_daily_pnl(self, account_type: str) -> float:
        """Get today's P&L: closed trades from DB + unrealized from open positions.

        The DB query runs in a thread (blocking SQLite call).  Unrealized PnL is
        computed back on the event loop so we can safely read self.positions
        and self.last_tick_prices without any cross-thread data races.
        """

        closed_pnl = await self._get_realized_daily_pnl(account_type)

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

    async def _restore_session_pnl_from_ledger(self) -> float:
        """Rebuild restart-safe session PnL from today's authoritative closed ledger rows."""
        active_broker = str(getattr(self, "active_broker", "IBKR")).upper()
        account_type = "mt5" if active_broker == "MT5" else "ibkr"
        realized_pnl = await self._get_realized_daily_pnl(account_type)
        self.session_pnl = realized_pnl
        logger.info(
            "Session PnL restored from today's closed %s ledger rows: $%+.2f",
            account_type.upper(),
            realized_pnl,
        )
        return realized_pnl

    async def _update_drawdowns(self) -> None:
        """Update drawdown ladders from current account values."""
        ibkr_equity = await self._get_account_value("ibkr")
        ibkr_metadata = self._account_value_metadata("ibkr")
        ibkr_authoritative = bool(ibkr_metadata["authoritative"]) and ibkr_equity > 0
        if ibkr_authoritative:
            self.ibkr_drawdown.update(ibkr_equity)
        if self.db_conn:
            cursor = None
            try:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("last_heartbeat", time.time_ns()),
                )
                if ibkr_authoritative:
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                        ("peak_equity", str(self.ibkr_drawdown.peak_equity)),
                    )
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                        ("peak_equity_source", str(ibkr_metadata["source"])),
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
        mt5_metadata = self._account_value_metadata("mt5")
        if bool(mt5_metadata["authoritative"]) and mt5_equity > 0:
            self.prop_drawdown.update(mt5_equity)
