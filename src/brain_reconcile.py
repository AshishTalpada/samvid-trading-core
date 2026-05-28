"""Broker reconciliation logic extracted from brain.py.

This module provides a BrokerReconciler mixin that TradingBrain can inherit from
to keep position-synchronization concerns separate from scanning / trading logic.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from system_types import Position

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _safe_entry_time(entry_time_value: datetime | str | int | float | None) -> datetime:
    """Safely convert any entry_time to tz-aware datetime.

    Prevents 'str' object has no attribute 'tzinfo' errors during reconciliation.
    On corruption, logs the issue and returns epoch minimum.
    """
    if isinstance(entry_time_value, str):
        try:
            cleaned = entry_time_value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
        except Exception as e:
            logger.warning(
                "_safe_entry_time: corrupted string timestamp %r: %s. Defaulting to epoch.",
                entry_time_value,
                e,
            )
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(entry_time_value, (int, float)):
        ts = float(entry_time_value)
        if ts > 10_000_000_000_000_000:
            return datetime.fromtimestamp(ts / 1_000_000_000, tz=timezone.utc)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(entry_time_value, datetime):
        if entry_time_value.tzinfo is None:
            return entry_time_value.replace(tzinfo=timezone.utc)
        return entry_time_value
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


class BrokerReconciler:
    """Mixin: restores, sanitizes, and reconciles internal positions with broker reality."""

    # ------------------------------------------------------------------
    # Position restore / sanitize
    # ------------------------------------------------------------------
    async def _restore_positions_from_db(self) -> None:
        """Restore OPEN positions from prior sessions and clean up orphans."""

        def _sync_restore() -> None:
            cursor = None
            try:
                if not self.db_conn:
                    return
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "SELECT id, timestamp, instrument, entry_price, stop_price, target_price, "
                    "shares, r_r_ratio, pattern, regime, broker, account_id, trading_mode, "
                    "direction "
                    "FROM trades WHERE outcome = 'OPEN' ORDER BY id DESC"
                )
                rows = cursor.fetchall()
                if not rows:
                    logger.info("No orphaned OPEN positions found — clean start.")
                    return

                restored = 0
                orphaned = 0
                seen_symbols: set = set()

                for row in rows:
                    (
                        tid,
                        ts_str,
                        symbol,
                        entry,
                        stop,
                        target,
                        qty,
                        rr,
                        pattern,
                        regime,
                        broker,
                        acc_id,
                        _tmode,
                        direction_col,
                    ) = row

                    try:
                        cleaned_ts = str(ts_str).replace("Z", "+00:00")
                        entry_time = datetime.fromisoformat(cleaned_ts)
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=timezone.utc)
                    except Exception:
                        entry_time = datetime.now(timezone.utc)

                    age_hours = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600

                    if age_hours > 720 or (symbol, broker) in seen_symbols:
                        cursor.execute(
                            "UPDATE trades SET outcome = 'ORPHANED', notes = ? WHERE id = ?",
                            (f"Orphaned on restart after {age_hours:.1f}h or duplicate", tid),
                        )
                        orphaned += 1
                        continue

                    entry_f = float(entry) if entry else 0.0
                    stop_f = float(stop) if stop else 0.0
                    qty_raw = float(qty) if qty else 0.0
                    is_short = str(direction_col or "").upper() == "SHORT"
                    qty_f = -abs(qty_raw) if is_short else abs(qty_raw)
                    if entry_f <= 0.0 or qty_raw == 0.0:
                        cursor.execute(
                            "UPDATE trades SET outcome = 'ORPHANED', notes = ? WHERE id = ?",
                            (f"Corrupt restore: entry_price={entry_f} qty={qty_f}", tid),
                        )
                        orphaned += 1
                        logger.warning(
                            "Orphaned corrupt position %s (id=%s): entry=%s, qty=%s",
                            symbol,
                            tid,
                            entry_f,
                            qty_f,
                        )
                        continue

                    seen_symbols.add((symbol, broker))
                    pos = Position(
                        symbol=symbol,
                        qty=qty_f,
                        entry_price=entry_f,
                        entry_time=entry_time,
                        pattern=pattern or "Unknown",
                        initial_belief=0.50,
                        current_belief=0.50,
                        initial_stop=stop_f if stop_f > 0 else entry_f * 0.99,
                        stop_loss=stop_f if stop_f > 0 else entry_f * 0.99,
                        take_profit=float(target) if target else entry_f * 1.02,
                        target_exit_time=datetime.now(timezone.utc) + timedelta(days=5),
                        trade_id=f"RESTORED-{tid}",
                        account_type=broker or "ibkr",
                        account_id=acc_id or "UNKNOWN",
                        catalyst_score=70.0,
                        dhatu_state="Restored",
                        regime_at_entry=regime or "UNKNOWN",
                        r_r_ratio=float(rr) if rr else 2.0,
                    )
                    self.positions.append(pos)
                    restored += 1

                self.db_conn.commit()

                if restored:
                    logger.info(
                        "RESTORED %s position(s) from prior session: %s",
                        restored,
                        [p.symbol for p in self.positions],
                    )
                if orphaned:
                    logger.info("Marked %s old/duplicate trade(s) as ORPHANED", orphaned)

            except Exception as e:
                logger.error("Position restoration failed: %s", e)
            finally:
                if cursor is not None:
                    cursor.close()

        await asyncio.to_thread(_sync_restore)  # type: ignore[arg-type]
        self._sanitize_positions()
        await self._reconcile_broker_positions()

    def _sanitize_positions(self) -> None:
        """Imperial Integrity Check: Purges non-object entries from memory pool."""
        valid = []
        for p in self.positions:
            if hasattr(p, "symbol") and not isinstance(p, dict):
                try:
                    p.__post_init__()
                except Exception as _e:
                    logger.debug("_sanitize_positions: __post_init__ failed: %s", _e)
                valid.append(p)
            elif isinstance(p, dict) and "symbol" in p:
                try:
                    from dataclasses import fields

                    from system_types import Position

                    field_names = {f.name for f in fields(Position)}
                    filtered = {k: v for k, v in p.items() if k in field_names}
                    valid.append(Position(**filtered))
                    logger.warning("SANITIZER: Re-hydrated dictionary for %s.", p["symbol"])
                except Exception:
                    continue
        self.positions = valid

    # ------------------------------------------------------------------
    # Broker reconciliation
    # ------------------------------------------------------------------
    async def _reconcile_broker_positions(self) -> None:
        """
        Sovereign Reconciliation Cycle: Dual-Broker Reality Handshake.
        Synchronizes internal memory with BOTH IBKR and MT5 realities.
        """
        try:
            ibkr_reality: dict[str, float] = {}
            ibkr_polled = False
            if self._broker_is_connected(self.ibkr_conn):
                ibkr_reality = self.ibkr_conn._positions_cache
                memory_ibkr_count = len([p for p in self.positions if p.account_type == "ibkr"])
                if not ibkr_reality or len(ibkr_reality) < memory_ibkr_count:
                    logger.debug(
                        "IBKR SYNC: Cache incomplete (%s vs %s). Forcing reality poll...",
                        len(ibkr_reality),
                        memory_ibkr_count,
                    )
                    try:
                        positions_callable = getattr(self.ibkr_conn.ib, "positions", None)
                        if positions_callable is not None and callable(positions_callable):
                            actual_pos = await asyncio.to_thread(positions_callable)
                            self.ibkr_conn._positions_cache.clear()
                            for p in actual_pos:
                                self.ibkr_conn._positions_cache[p.contract.symbol] = p.position
                            ibkr_reality = self.ibkr_conn._positions_cache
                            ibkr_polled = True
                    except Exception as sync_e:
                        logger.warning("IBKR SYNC: Reality poll failed: %s", sync_e)

            mt5_reality: dict[str, float] = {}
            mt5_polled = False
            if self._broker_is_connected(self.mt5_conn):
                if hasattr(self.mt5_conn, "get_all_positions") and callable(
                    getattr(self.mt5_conn, "get_all_positions", None)
                ):
                    mt5_reality = await asyncio.to_thread(self.mt5_conn.get_all_positions)
                    mt5_polled = True
                else:
                    logger.warning(
                        "MT5 get_all_positions not callable, skipping MT5 reconciliation"
                    )

            self._sanitize_positions()

            now_ts = datetime.now(timezone.utc)
            uptime = (
                (now_ts - self.start_time).total_seconds() if hasattr(self, "start_time") else 0.0
            )

            for p in list(self.positions):
                broker = p.account_type
                reality = ibkr_reality if broker == "ibkr" else mt5_reality
                polled = ibkr_polled if broker == "ibkr" else mt5_polled

                if p.symbol not in reality:
                    if not polled:
                        continue

                    _p_entry = _safe_entry_time(p.entry_time)
                    age_seconds = (now_ts - _p_entry).total_seconds()

                    if age_seconds < 120:
                        continue
                    broker_qty = 0.0
                else:
                    broker_qty = reality[p.symbol]

                _p_entry = _safe_entry_time(p.entry_time)
                age_seconds = (now_ts - _p_entry).total_seconds()

                # Purge threshold: 60s uptime if symbol is completely absent from broker,
                # or 300s if it's present but shows qty=0 (could be a brief fill delay).
                symbol_absent_from_broker = p.symbol not in (ibkr_reality if broker == "ibkr" else mt5_reality)
                purge_uptime_threshold = 60 if symbol_absent_from_broker else 300
                purge_age_threshold = 60 if symbol_absent_from_broker else 300
                if uptime > purge_uptime_threshold and age_seconds > purge_age_threshold and abs(broker_qty) < 0.1:
                    logger.warning(
                        "SYNC PURGE [%s]: %s is flat in reality. Removing from memory.",
                        broker.upper(),
                        p.symbol,
                    )
                    if p in self.positions:
                        self.positions.remove(p)
                    self._mark_trade_liquidated(p.symbol, broker)
                    continue

                if p.symbol in reality and abs(p.qty - broker_qty) > 0.00001:
                    if age_seconds > 60:
                        p.qty = float(broker_qty)
                        self._update_trade_volume(p.symbol, broker, p.qty)

            # Reality report
            report_lines = [
                "\n" + "=" * 80,
                "   SOVEREIGN REALITY HANDSHAKE (Memory vs Broker) ",
                "=" * 80,
                f" {'Symbol':<10} | {'Broker':<8} | {'Memory Qty':<12} | "
                f"{'Reality Qty':<12} | {'Status':<10}",
                "-" * 80,
            ]

            all_symbols = (
                set(ibkr_reality.keys())
                | set(mt5_reality.keys())
                | {p.symbol for p in self.positions}
            )
            for sym in sorted(all_symbols):
                for b in ("ibkr", "mt5"):
                    reality_map = ibkr_reality if b == "ibkr" else mt5_reality
                    if b == "mt5" and not self._broker_is_connected(self.mt5_conn):
                        continue

                    m_pos = next(
                        (p for p in self.positions if p.symbol == sym and p.account_type == b), None
                    )
                    m_qty = m_pos.qty if m_pos else 0.0
                    r_qty = reality_map.get(sym, 0.0)

                    if abs(m_qty) < 0.01 and abs(r_qty) < 0.01:
                        continue

                    status = " MATCH" if abs(m_qty - r_qty) < 0.0001 else " DRIFT"
                    report_lines.append(
                        f" {sym:<10} | {b:<8} | {m_qty:<12.2f} | {r_qty:<12.2f} | {status}"
                    )

            report_lines.append("=" * 80 + "\n")
            drift_found = any("DRIFT" in line for line in report_lines)
            position_rows = max(0, len(report_lines) - 6)
            last_report = getattr(self, "_last_reality_report_ts", 0.0)
            market_open = self._is_market_open()
            quiet_empty_after_hours = not market_open and position_rows == 0 and not drift_found
            report_interval = 900 if quiet_empty_after_hours else 60
            if drift_found or time.monotonic() - last_report > report_interval:
                report_logger = logger.debug if quiet_empty_after_hours else logger.info
                report_logger("\n".join(report_lines))
                self._last_reality_report_ts = time.monotonic()

            self._reconcile_open_trade_rows("ibkr", ibkr_reality, ibkr_polled, now_ts)
            self._reconcile_open_trade_rows("mt5", mt5_reality, mt5_polled, now_ts)

            # Adoption Protocol
            all_managed = {(p.symbol, p.account_type) for p in self.positions}
            for symbol, qty in ibkr_reality.items():
                if abs(qty) >= 0.1 and (symbol, "ibkr") not in all_managed:
                    await self._adopt_orphan(symbol, qty, "ibkr")
            for symbol, qty in mt5_reality.items():
                if abs(qty) >= 0.01 and (symbol, "mt5") not in all_managed:
                    await self._adopt_orphan(symbol, qty, "mt5")

        except Exception as e:
            logger.error("Sovereign Reconciliation Failed: %s", e, exc_info=True)

    def _reconcile_open_trade_rows(
        self,
        broker: str,
        reality: dict[str, float],
        polled: bool,
        now_ts: datetime,
    ) -> None:
        """Close stale OPEN rows when a fresh broker poll proves the broker is flat."""
        if not self.db_conn or not polled:
            return

        cursor = None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT id, timestamp, instrument, entry_price, shares FROM trades "
                "WHERE broker = ? AND outcome = 'OPEN'",
                (broker,),
            )
            # stale_trades: list of (trade_id, instrument, entry_price, shares)
            stale_trades: list[tuple[int, str, float, float]] = []
            for tid, ts_str, symbol, entry_price_raw, shares_raw in cursor.fetchall():
                if abs(float(reality.get(symbol, 0.0) or 0.0)) >= 0.1:
                    continue

                age_seconds = 999999.0
                try:
                    raw_str = str(ts_str)
                    if isinstance(ts_str, (int, float)) or raw_str.isdigit():
                        raw_ts = int(ts_str)
                        if raw_ts > 10_000_000_000_000_000:
                            opened_at = datetime.fromtimestamp(
                                raw_ts / 1_000_000_000, tz=timezone.utc
                            )
                        else:
                            opened_at = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
                    else:
                        opened_at = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
                        if opened_at.tzinfo is None:
                            opened_at = opened_at.replace(tzinfo=timezone.utc)
                    age_seconds = (now_ts - opened_at).total_seconds()
                except Exception as _e:
                    logger.debug("Reconciliation: timestamp parse failed: %s", _e)

                if age_seconds >= 120:
                    entry_price = float(entry_price_raw) if entry_price_raw is not None else 0.0
                    shares = float(shares_raw) if shares_raw is not None else 0.0
                    stale_trades.append((int(tid), symbol or "", entry_price, shares))

            if stale_trades:
                for trade_id, instrument, entry_price, shares in stale_trades:
                    # Resolve current market price for exit_price
                    exit_price = 0.0
                    try:
                        exit_price = float(
                            getattr(self, "last_tick_prices", {}).get(instrument, 0.0) or 0.0
                        )
                        if exit_price <= 0 and hasattr(self, "data_pipeline"):
                            dp_price = self.data_pipeline.get_last_price(instrument)
                            if dp_price:
                                exit_price = float(dp_price)
                    except Exception as _price_err:
                        logger.debug(
                            "Reconciliation: price lookup failed for %s: %s",
                            instrument,
                            _price_err,
                        )

                    # Rough P&L: (exit - entry) x shares
                    pnl = (exit_price - entry_price) * shares if exit_price > 0 else 0.0
                    if pnl > 0:
                        db_outcome = "WIN"
                    elif pnl < 0:
                        db_outcome = "LOSS"
                    else:
                        db_outcome = "BREAKEVEN"

                    cursor.execute(
                        "UPDATE trades SET outcome = ?, exit_price = ?, pnl_dollars = ?, "
                        "net_pnl = ?, notes = COALESCE(notes || ' | ', '') || ? "
                        "WHERE id = ?",
                        (
                            db_outcome,
                            exit_price if exit_price > 0 else None,
                            pnl,
                            pnl,
                            "LIQUIDATED: broker reality flat during reconciliation",
                            trade_id,
                        ),
                    )

                self.db_conn.commit()
                logger.warning(
                    "Reconciliation: marked %s stale %s OPEN trade row(s) "
                    "LIQUIDATED after fresh broker poll.",
                    len(stale_trades),
                    broker.upper(),
                )
        except Exception as exc:
            logger.debug("DB open-trade reconciliation failed for %s: %s", broker, exc)
        finally:
            if cursor is not None:
                cursor.close()

    async def _adopt_orphan(self, symbol: str, qty: float, broker: str) -> None:
        """Absorb an unmanaged broker position into the Matrix."""
        logger.warning(
            "ORPHAN DETECTED [%s]: %s | Qty: %s. Initiating Adoption...",
            broker.upper(),
            symbol,
            qty,
        )
        try:
            price = self.last_tick_prices.get(symbol, 0.0)
            if price <= 0:
                market_data = await self._fetch_market_snapshot(symbol)
                raw_price = market_data.get("price") if market_data else None
                price = float(raw_price) if raw_price is not None else 0.0

            direction = "LONG" if qty > 0 else "SHORT"

            db_row = None
            if self.db_conn:
                cursor = self.db_conn.cursor()
                try:
                    cursor.execute(
                        "SELECT entry_price, stop_price, target_price FROM trades "
                        "WHERE instrument=? AND broker=? AND outcome='OPEN' ORDER BY id DESC LIMIT 1",
                        (symbol, broker),
                    )
                    db_row = cursor.fetchone()
                finally:
                    cursor.close()

            if db_row:
                entry, stop, target = db_row
                stop = stop or (entry * 0.98 if qty > 0 else entry * 1.02)
                target = target or (entry * 1.05 if qty > 0 else entry * 0.95)
            else:
                entry = price if price > 0 else 0.0
                stop = entry * 0.985 if qty > 0 else entry * 1.015
                target = entry * 1.10 if qty > 0 else entry * 0.90

            from system_types import Position

            adopted = Position(
                symbol=symbol,
                qty=qty,
                entry_price=entry,
                entry_time=datetime.now(timezone.utc),
                pattern="ADOPTED_ORPHAN",
                stop_loss=stop,
                initial_stop=stop,
                take_profit=target,
                trade_id=f"ADOPTED-{broker.upper()}-{symbol}",
                account_type=broker,
                meta={"adoption_ts": time.time_ns()},
            )

            self.positions.append(adopted)

            if self.db_conn and not db_row:
                cursor = self.db_conn.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO trades (timestamp, instrument, direction, shares, entry_price, "
                        "outcome, stop_price, target_price, broker, notes) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            datetime.now(timezone.utc).isoformat(),
                            symbol,
                            direction,
                            abs(qty),
                            price,
                            "OPEN",
                            stop,
                            target,
                            broker,
                            "Sovereign Adoption Protocol v1.0-beta",
                        ),
                    )
                    adopted.db_id = cursor.lastrowid
                    self.db_conn.commit()
                finally:
                    cursor.close()

            logger.info("ADOPTED: %s in %s absorbed @ %.2f", symbol, broker.upper(), price)

            if (
                self.bus
                and hasattr(self.bus, "publish")
                and callable(getattr(self.bus, "publish", None))
            ):
                await self.bus.publish(
                    "notification.telegram",
                    {
                        "message": (
                            f" *ORPHAN ADOPTED*\nBroker: {broker.upper()}\n"
                            f"Symbol: {symbol}\nQty: {qty}\nStop: {stop:.2f}"
                        )
                    },
                )

        except Exception as e:
            logger.error("Failed to adopt orphan %s on %s: %s", symbol, broker, e)

    def _mark_trade_liquidated(self, symbol: str, broker: str) -> None:
        """Update DB to reflect that a trade is no longer open."""
        try:
            if self.db_conn:
                self.db_conn.execute(
                    "UPDATE trades SET outcome = 'LIQUIDATED' WHERE instrument = ? "
                    "AND broker = ? AND outcome = 'OPEN'",
                    (symbol, broker),
                )
                self.db_conn.commit()
        except Exception as e:
            logger.debug("DB mark_liquidated failed for %s on %s: %s", symbol, broker, e)

    def _update_trade_volume(self, symbol: str, broker: str, qty: float) -> None:
        """Update DB with actual volume from broker reality."""
        try:
            if self.db_conn:
                self.db_conn.execute(
                    "UPDATE trades SET shares = ? WHERE instrument = ? "
                    "AND broker = ? AND outcome = 'OPEN'",
                    (abs(qty), symbol, broker),
                )
                self.db_conn.commit()
        except Exception as e:
            logger.debug("DB update_trade_volume failed for %s on %s: %s", symbol, broker, e)
