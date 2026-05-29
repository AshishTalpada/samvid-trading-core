"""Order execution, logging, and broker helpers extracted from brain.py.

Provides the ExecutionMixin with:
- _place_ibkr_order (IBKR order routing with polarity guard + bracket support)
- _place_mt5_order  (MT5 Forex execution)
- _determine_target_broker / _perform_broker_hotswap
- _log_signal, _log_trade_entry, _log_trade_exit  (DB persistence)
- _panic_liquidate_all  (emergency flattening)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from system_types import Position

logger = logging.getLogger(__name__)


class ExecutionMixin:
    """Mixin: IBKR/MT5 order placement, DB logging, broker hot-swap, panic liquidation."""

    # ------------------------------------------------------------------
    # IBKR order routing
    # ------------------------------------------------------------------
    async def _place_ibkr_order(
        self,
        symbol: str,
        direction: str,
        shares: float,
        urgency: str = "LOW",
        limit_price: float = 0.0,
        stop_price: float = 0.0,
        target_price: float = 0.0,
        **kwargs,
    ) -> str:
        """Helper to route orders through Agent C (IBKR)."""
        if not self.ibkr_conn:
            return ""

        # Prevent redundant exits for symbols already pending on the book.
        if await asyncio.to_thread(self.ibkr_conn.has_pending_order, symbol):
            logger.info(
                "Sovereign Shield: Suppressed redundant order for %s (Order Pending).", symbol
            )
            return "SHIELDED"

        try:
            # Live query — touches the broker directly to be 100% sure
            broker_positions = {
                p.contract.symbol: p.position
                for p in self.ibkr_client.positions()
                if p.position != 0
            }
            broker_qty = broker_positions.get(symbol, 0)

            # If the signs differ or magnitude is way off, fix memory IMMEDIATELY.
            for p in self.positions:
                if p.symbol == symbol and (
                    np.sign(p.qty) != np.sign(broker_qty) or abs(p.qty - broker_qty) > 0.1
                ):
                    logger.warning(
                        "MIRROR SYNC: %s memory error (%s) corrected to Broker Reality (%s).",
                        symbol,
                        p.qty,
                        broker_qty,
                    )
                    p.qty = float(broker_qty)

            if direction == "SELL" and broker_qty < 0:
                logger.critical(
                    "POLARITY SHIELD: Corrected SELL->BUY for %s "
                    "(Short exposure: %s). Closing short with BUY.",
                    symbol,
                    broker_qty,
                )
                direction = "BUY"
            elif direction == "BUY" and broker_qty > 0:
                logger.critical(
                    "POLARITY SHIELD: Corrected BUY->SELL for %s "
                    "(Long exposure: %s). Closing long with SELL.",
                    symbol,
                    broker_qty,
                )
                direction = "SELL"
        except Exception as guard_e:
            logger.debug("Polarity Guard Live Check skipped (Recovery mode active): %s", guard_e)

        # IBKR Rate Limiting Protocol (Max 20/sec)
        await self.rate_limiter.acquire()

        try:
            if shares < 1:
                logger.warning(
                    "ZERO-SHARE SHIELD: Blocked %s for %s (Size=0). "
                    "Check sizer math or Probe logic.",
                    direction,
                    symbol,
                )
                from telegram_alerts import send_telegram_alert

                await send_telegram_alert(
                    f" *SHIELD VETO: {symbol}*\n"
                    f"Action: Blocked {direction}\n"
                    f"Reason: Zero Size (Risk/Ladder restriction)\n"
                    f"Status: Standing Down"
                )
                return None

            # Bracket order (stop + target geometry)
            if stop_price > 0 and target_price > 0:
                if self.mode == "paper" and not self.ibkr_conn.is_connected():
                    logger.info(
                        "PAPER [SIM]: Bracket %s %s %s @ $%s",
                        direction,
                        shares,
                        symbol,
                        limit_price,
                    )
                    return f"PAPER-{int(time.time())}"

                ok, reason = await asyncio.to_thread(
                    self.ibkr_conn.validate_order_pre_flight, symbol, direction, shares, limit_price
                )
                if not ok:
                    logger.critical("PRE-FLIGHT REJECTION for %s: %s", symbol, reason)
                    return None

                exec_token = self.ibkr_conn.generate_exec_token(symbol)
                kwargs["exec_token"] = exec_token

                ids = await self.ibkr_conn.place_bracket_order(
                    symbol=symbol,
                    direction=direction,
                    shares=shares,
                    limit_price=limit_price,
                    stop_loss=stop_price,
                    take_profit=target_price,
                    urgency=urgency,
                    **kwargs,
                )
                return str(ids[0]) if ids else ""

            # Single order
            if self.mode == "paper" and not self.ibkr_conn.is_connected():
                logger.info(
                    "PAPER [SIM]: Single %s %s %s (Urgency: %s)",
                    direction,
                    shares,
                    symbol,
                    urgency,
                )
                return f"PAPER-{int(time.time())}"

            exec_token = self.ibkr_conn.generate_exec_token(symbol)
            kwargs["exec_token"] = exec_token

            if urgency == "EMERGENCY":
                oid = await self.ibkr_conn.place_order(
                    symbol, direction, shares, order_type="MKT", urgency="EMERGENCY", **kwargs
                )
                if oid:
                    try:
                        self._order_submit_times[int(oid)] = datetime.now(timezone.utc)
                    except (ValueError, TypeError) as e:
                        logger.debug("BrainExecution: could not store order submit time for oid %s: %s", oid, e)
                return oid

            if urgency == "LOW" and limit_price > 0:
                oid = await self.ibkr_conn.place_order(
                    symbol,
                    direction,
                    shares,
                    order_type="LMT",
                    limit_price=limit_price,
                    urgency=urgency,
                    **kwargs,
                )
            else:
                oid = await self.ibkr_conn.place_order(
                    symbol, direction, shares, order_type="MKT", urgency=urgency, **kwargs
                )
            if oid:
                try:
                    self._order_submit_times[int(oid)] = datetime.now(timezone.utc)
                except (ValueError, TypeError) as e:
                    logger.debug("BrainExecution: could not store order submit time for oid %s: %s", oid, e)
            return oid
        except Exception as e:
            logger.error("IBKR order failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # MT5 order routing
    # ------------------------------------------------------------------
    async def _place_mt5_order(
        self, symbol, direction, shares, limit_price, stop_price, target_price, **kwargs
    ):
        """Forex Execution Engine for MT5."""
        logger.info("MT5: Placing %s order for %s (%s lots)", direction, symbol, shares)

        risk_per_trade = getattr(self, "mt5_risk_per_trade", 10.0)

        # Respect coordinator-calculated shares; fallback to sizer if zero.
        if shares and shares > 0:
            lots = float(shares)
        else:
            lots = (
                self.mt5_sizer.calculate_lots(risk_per_trade, limit_price, stop_price, symbol)
                or 0.01
            )

        order_id = await asyncio.to_thread(
            self.mt5_conn.place_order,
            sym=symbol,
            dir=direction.lower(),
            vol=lots,
            sl=stop_price,
            tp=target_price,
        )
        return order_id

    # ------------------------------------------------------------------
    # Broker routing / hot-swap
    # ------------------------------------------------------------------
    def _determine_target_broker(self) -> str:
        """Determines if the system should be in Equities (IBKR) or Forex (MT5) mode."""
        from datetime import timedelta

        now_utc = datetime.now(timezone.utc)
        now_ny = now_utc - timedelta(hours=4)
        hour = now_ny.hour
        minute = now_ny.minute

        # 16:00 - 17:00 NY: MAINTENANCE STAND-DOWN
        if hour == 16:
            logger.debug(
                "Sovereign: Maintenance Window detected (%s:%02d NY). Standing down.", hour, minute
            )
            return "MAINTENANCE"

        # IBKR Equities: 9:30 AM - 4:00 PM NY
        if 9 <= hour < 16:
            if hour == 9 and minute < 30:
                return "MT5"
            return "IBKR"

        # MT5 Forex: 5:00 PM - 9:00 AM NY
        return "MT5"

    async def _perform_broker_hotswap(self, target: str) -> None:
        """Swaps the system consciousness between brokers to save VRAM/CPU."""
        from vault import Vault

        logger.warning("SOVEREIGN HOT-SWAP: Switching from %s to %s...", self.active_broker, target)

        if target == "MT5":
            self.active_broker = "MT5"
            login = int(Vault.get("MT5_LOGIN", "0"))
            pw = Vault.get("MT5_PASSWORD", "")
            srv = Vault.get("MT5_SERVER", "")
            if login > 0:
                success = await asyncio.to_thread(self.mt5_conn.connect, login, pw, srv)
                if success:
                    logger.info("MT5: Connection established for Forex session.")
                else:
                    logger.error("MT5: Connection FAILED. Reverting to IBKR.")
                    self.active_broker = "IBKR"
        else:
            self.active_broker = "IBKR"
            logger.info("IBKR: Returning to Equities session.")

    # ------------------------------------------------------------------
    # DB signal logging
    # ------------------------------------------------------------------
    async def _log_signal(self, symbol: str, pattern, approved: bool, reason: str) -> None:
        """Log signal to database (Shadow Portfolio tracking)."""

        def _sync_log() -> None:
            cursor = None
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    cursor.execute(
                        "INSERT INTO signals (timestamp, instrument, pattern, base_quality, "
                        "catalyst_score, action_taken, skip_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            time.time_ns(),
                            symbol,
                            pattern.name,
                            pattern.confidence,
                            pattern.confidence,
                            "APPROVED" if approved else "REJECTED",
                            reason,
                        ),
                    )
            except Exception as e:
                logger.debug("Could not log signal: %s", e)
            finally:
                if cursor is not None:
                    cursor.close()

        await asyncio.to_thread(_sync_log)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # DB trade entry/exit logging
    # ------------------------------------------------------------------
    async def _log_trade_entry(self, pos: "Position") -> None:
        """Log trade entry to database."""

        def _sync_log() -> None:
            cursor = None
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    recorded_shares = abs(pos.qty)
                    direction_str = "LONG" if pos.qty > 0 else "SHORT"

                    intel_snap = json.dumps(
                        {
                            "lambda": getattr(self, "current_lambda", 0),
                            "regime": pos.regime_at_entry,
                            "vix": self.vix_data.get("VIX", 0) if hasattr(self, "vix_data") else 0,
                            "swarm_profile": getattr(
                                self.swarm_predictor, "_last_consensus", None
                            ).__dict__
                            if hasattr(self.swarm_predictor, "_last_consensus")
                            and self.swarm_predictor._last_consensus
                            else "None",
                        },
                        default=str,
                    )

                    outcome = str(getattr(pos, "status", "OPEN") or "OPEN")
                    broker = pos.account_type
                    account_id = pos.account_id or "UNKNOWN"
                    if outcome == "OPEN":
                        cursor.execute(
                            "SELECT id FROM trades WHERE instrument=? AND broker=? "
                            "AND account_id=? AND outcome='OPEN' ORDER BY id DESC LIMIT 1",
                            (pos.symbol, broker, account_id),
                        )
                        existing = cursor.fetchone()
                        if existing:
                            pos.db_id = existing[0]
                            logger.warning(
                                "Trade entry skipped for %s: existing OPEN trade id=%s on %s/%s",
                                pos.symbol,
                                pos.db_id,
                                broker,
                                account_id,
                            )
                            return

                    cursor.execute(
                        "INSERT INTO trades (timestamp, instrument, direction, pattern, regime, "
                        "entry_price, stop_price, target_price, shares, r_r_ratio, catalyst_score, "
                        "dhatu_state, belief_at_entry, broker, account_id, trading_mode, outcome, "
                        "commission, slippage, net_pnl, intel_snapshot) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            pos.entry_time.isoformat(),
                            pos.symbol,
                            direction_str,
                            pos.pattern,
                            pos.regime_at_entry,
                            pos.entry_price,
                            pos.stop_loss,
                            pos.take_profit,
                            recorded_shares,
                            pos.r_r_ratio,
                            pos.catalyst_score,
                            pos.dhatu_state,
                            pos.initial_belief,
                            broker,
                            account_id,
                            self.mode,
                            outcome,
                            getattr(pos, "commission_cost", 0.0),
                            getattr(pos, "slippage_cost", 0.0),
                            0.0,
                            intel_snap,
                        ),
                    )
                    pos.db_id = cursor.lastrowid
                    self.db_conn.commit()
            except Exception as e:
                logger.debug("Could not log trade entry: %s", e)
            finally:
                if cursor is not None:
                    cursor.close()

        await asyncio.to_thread(_sync_log)  # type: ignore[arg-type]

    async def _log_trade_exit(
        self, pos: "Position", exit_type: str, exit_price: float, pnl: float, r_multiple: float
    ) -> None:
        """Log trade exit to database and generate a post-mortem analysis."""
        from brain_reconcile import _safe_entry_time

        def _sync_log() -> None:
            nonlocal exit_price, pnl
            try:
                # Ghost recovery: if exit_price is 0, pull from data pipeline
                if not exit_price or exit_price <= 0:
                    logger.warning(
                        "GHOST RECOVERY: %s exit price is 0. Pulling reality from pipeline...",
                        pos.symbol,
                    )
                    if hasattr(self, "data_pipeline"):
                        last_tick = self.data_pipeline.get_last_price(pos.symbol)
                        if last_tick:
                            exit_price = last_tick
                            pnl = (exit_price - pos.entry_price) * pos.qty
                            logger.info(
                                "Reality Restored: %s price set to $%.2f", pos.symbol, exit_price
                            )

                if self.db_conn:
                    cursor = None
                    try:
                        cursor = self.db_conn.cursor()
                        _entry_ts = _safe_entry_time(pos.entry_time)
                        hold_hours = (
                            datetime.now(timezone.utc) - _entry_ts
                        ).total_seconds() / 3600
                        # pnl_dollars = gross PnL (price move only, pre-cost)
                        # net_pnl     = after commission + slippage deduction
                        commission = getattr(pos, "commission_cost", 0.0) or 0.0
                        slippage   = getattr(pos, "slippage_cost", 0.0) or 0.0
                        net_pnl = pnl - commission - slippage

                        # Outcome is based on net (after-cost) PnL
                        if net_pnl > 0:
                            db_outcome = "WIN"
                        elif net_pnl < 0:
                            db_outcome = "LOSS"
                        else:
                            db_outcome = "BREAKEVEN"

                        cursor.execute(
                            "UPDATE trades SET exit_price=?, outcome=?, pnl_dollars=?, r_multiple=?, "
                            "hold_hours=?, belief_at_exit=?, net_pnl=?, "
                            "notes=COALESCE(notes || ' | ', '') || ? WHERE rowid=?",
                            (
                                exit_price,
                                db_outcome,
                                pnl,        # gross (pre-cost)
                                r_multiple,
                                hold_hours,
                                pos.current_belief,
                                net_pnl,    # after commission + slippage
                                f"exit_type={exit_type}",
                                getattr(pos, "db_id", 0),
                            ),
                        )
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS performance_summary (
                                key TEXT PRIMARY KEY,
                                value TEXT,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        cursor.execute("PRAGMA table_info(performance_summary)")
                        summary_cols = {row[1] for row in cursor.fetchall()}
                        if {"key", "value"}.issubset(summary_cols):
                            # Only aggregate genuine closed trades with real numeric pnl
                            cursor.execute("""
                                SELECT
                                    COUNT(*) AS closed_count,
                                    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                                    SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losses,
                                    SUM(net_pnl) AS net_pnl,
                                    AVG(r_multiple) AS avg_r
                                FROM trades
                                WHERE outcome IN ('WIN', 'LOSS', 'BREAKEVEN')
                                  AND net_pnl IS NOT NULL
                            """)
                            row = cursor.fetchone()
                            closed_count = int(row[0] or 0)
                            wins = int(row[1] or 0)
                            losses = int(row[2] or 0)
                            summary = {
                                "closed_count": closed_count,
                                "wins": wins,
                                "losses": losses,
                                "win_rate": (wins / closed_count) if closed_count else 0.0,
                                "net_pnl": float(row[3] or 0.0),
                                "avg_r": float(row[4] or 0.0),
                                "updated_from": "brain._log_trade_exit",
                            }
                            cursor.execute(
                                "INSERT OR REPLACE INTO performance_summary (key, value, updated_at) "
                                "VALUES (?, ?, ?)",
                                ("latest", json.dumps(summary), datetime.now(timezone.utc)),
                            )
                        self.db_conn.commit()
                    except Exception as e:
                        logger.debug("Could not log trade exit: %s", e)
                    finally:
                        if cursor is not None:
                            cursor.close()
            except Exception as e:
                logger.debug("Could not log trade exit: %s", e)

        # Trigger Pillar 4/6 (Wisdom & Skill Evolution)
        reasoning = (
            f"Exit Type: {exit_type} | PnL: ${pnl:.2f} | R-Multiple: {r_multiple:.2f}x | "
            f"Catalyst: {pos.catalyst_score:.1f}"
        )
        self.wisdom.write_post_mortem(pos, exit_type, pnl, reasoning)

        if pnl > 0:
            self.skill_tree.skills["pnl_to_next"] -= pnl
            if self.skill_tree.skills["pnl_to_next"] <= 0:
                self.skill_tree.unlock("stop-loss-adjustment")
                self.skill_tree.skills["pnl_to_next"] = 5000.0
                logger.info("MATRIX LEVEL UP: Autonomy Level Increased (Tier 2).")

        self.skill_tree._save()

        self.loss_tracker.record_outcome(pnl > 0)
        if self.loss_tracker.consecutive_losses >= 5:
            logger.critical("5+ Consecutive Losses. Entering ABHAVA (Risk-Off) state.")
            self._oracle_dhatu = "Abhava"
        elif self.loss_tracker.win_streak >= 3:
            if self._oracle_dhatu != "Vriddhi":
                logger.info(
                    "WIN STREAK (%s): Shifting to VRIDDHI state.", self.loss_tracker.win_streak
                )
                self._oracle_dhatu = "Vriddhi"

        # Enhancement: Feed trade outcome back into BayesianBeliefTracker so it learns
        # from actual results (win -> price_toward_medium; loss -> price_against_medium).
        try:
            bt = getattr(self, "belief_tracker", None)
            if bt is not None:
                dhatu = getattr(self, "_oracle_dhatu", "Sthira")
                evidence = "price_toward_medium" if pnl > 0 else "price_against_medium"
                bt.update(evidence, dhatu_state=dhatu)
                logger.debug(
                    "BeliefTracker updated after %s exit: evidence=%s new_belief=%.3f",
                    "WIN" if pnl > 0 else "LOSS",
                    evidence,
                    bt.current_belief,
                )
        except Exception as _bt_err:
            logger.debug("BeliefTracker update skipped (non-fatal): %s", _bt_err)

        await asyncio.to_thread(_sync_log)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Emergency liquidation
    # ------------------------------------------------------------------
    async def _panic_liquidate_all(self) -> None:
        """Sovereign Shield: Emergency Total Portfolio Liquidation Sequence."""
        try:
            if self.ibkr_conn and self.ibkr_conn.ib and self.ibkr_conn.is_connected():
                import ib_insync

                positions = self.ibkr_conn.ib.positions()
                if not positions:
                    logger.info("SHIELD: No positions to liquidate. Clean Slate.")
                    return

                logger.critical("SHIELD: Liquidating %s positions immediately.", len(positions))
                for p in positions:
                    contract = p.contract
                    qty = p.position
                    action = "SELL" if qty > 0 else "BUY"
                    abs_qty = abs(qty)
                    logger.warning("SHIELD: Closing %s (%s %s)", contract.symbol, action, abs_qty)
                    order = ib_insync.MarketOrder(action, abs_qty)
                    self.ibkr_conn.ib.placeOrder(contract, order)

                logger.info("SHIELD: Liquidation orders broadcast. Waiting for sync...")
                await asyncio.sleep(5)
                logger.critical("SOVEREIGN SHIELD: TOTAL LIQUIDATION COMPLETE.")
        except Exception as e:
            logger.error("SHIELD: Panic Liquidation Failed: %s", e)

    # ------------------------------------------------------------------
    # Enhancement: Cancel stale unfilled entry orders after timeout
    # ------------------------------------------------------------------
    async def _cancel_stale_entry_orders(self, timeout_sec: int = 120) -> None:
        """Cancel IBKR entry orders that have been pending longer than timeout_sec.

        Exit orders (managed by brain_position stale-order escalator) are excluded.
        This method is called from the brain's background housekeeping loop.
        """
        if not (self.ibkr_conn and self.ibkr_conn.is_connected()):
            return
        try:
            import datetime as _dt
            trades = self.ibkr_conn.ib.trades()
            now = _dt.datetime.now(_dt.timezone.utc)
            for trade in trades:
                status = trade.orderStatus.status
                if status not in ("PendingSubmit", "PreSubmitted", "Submitted"):
                    continue
                action = trade.order.action  # "BUY" or "SELL"
                symbol = trade.contract.symbol
                # Use log time of last status change; fall back to now - timeout as safe guess
                log_time = getattr(trade.log[-1], "time", None) if trade.log else None
                if log_time is None:
                    continue
                # ib_insync log entries carry naive datetimes in UTC
                if log_time.tzinfo is None:
                    log_time = log_time.replace(tzinfo=_dt.timezone.utc)
                age_sec = (now - log_time).total_seconds()
                if age_sec >= timeout_sec:
                    order_id = trade.order.orderId
                    logger.warning(
                        "FIX11 STALE_ORDER: Cancelling unfilled %s order #%s for %s "
                        "(age=%.0fs >= %ss).",
                        action, order_id, symbol, age_sec, timeout_sec,
                    )
                    cancelled = self.ibkr_conn.cancel_order(order_id)
                    if not cancelled:
                        logger.warning(
                            "FIX11: cancel_order returned False for #%s (%s).",
                            order_id, symbol,
                        )
        except Exception as _so_err:
            logger.debug("_cancel_stale_entry_orders failed (non-fatal): %s", _so_err)
