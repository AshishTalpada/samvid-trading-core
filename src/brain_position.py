"""Position monitoring and exit processing extracted from brain.py.

Provides the PositionMonitor mixin with:
- _state_positioned: 7-level exit intelligence monitoring loop
- _state_exit: state machine exit handler
- _tool_get_account_status / _tool_get_open_positions: MindBridge tools
- _handle_emergency: flatten-all on critical error
- _process_exit: standardized exit resolver (Pillar 5)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from brain_fsm import TradingState
from brain_reconcile import _safe_entry_time
from decision_ledger import LEDGER
from exit_intelligence import ExitAction
from portfolio_analyzer import PORTFOLIO_ANALYZER
from system_types import Position

logger = logging.getLogger(__name__)


class PositionMonitor:
    """Mixin: position monitoring, exit processing, emergency flattening."""

    async def _state_positioned(self) -> None:
        """Monitor active positions using 7-Level Exit Intelligence Engine."""
        self._sanitize_positions()  # Ensure memory is objects, not dicts

        logger.debug(f"MONITORING {len(self.positions)} active positions")

        exits_triggered = []

        # PERF IMPLEMENT: fetch account equity & daily PnL once per monitoring cycle,
        # not once per position.  With 10 positions this was 20 DB queries per tick.
        _ibkr_equity = await self._get_account_value("ibkr")
        _ibkr_daily_pnl = await self._get_daily_pnl("ibkr")
        _mt5_equity = await self._get_account_value("mt5")
        _mt5_daily_pnl = await self._get_daily_pnl("mt5")

        for pos in list(self.positions):  # type: ignore
            if pos.meta.get("exit_triggered"):
                continue

            if abs(pos.qty) < 0.0001:
                # Ghost position (flattened externally). Skip monitoring to avoid 0-unit finalizations.
                continue

            try:
                # Fetch live market data for this position
                # SAFETY IMPLEMENT: wrap in 5-second timeout to prevent monitoring loop stall
                try:
                    market_data = await asyncio.wait_for(
                        self._fetch_market_snapshot(pos.symbol), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Market data timeout for %s — skipping this tick", pos.symbol)
                    continue
                current_price = (
                    market_data.get("price")
                    if market_data and market_data.get("price") is not None
                    else pos.entry_price
                )
                vix = market_data.get("vix", 18.0) if market_data else 18.0

                # Update Bayesian belief and real-time PnL
                pos.current_price = current_price
                pos.unrealized_pnl = (current_price - pos.entry_price) * pos.qty

                # Check IBKR cache to stop 'Phantom Tightening' logs
                broker_qty = None
                if pos.account_type == "ibkr" and self.ibkr_conn:
                    cache = getattr(self.ibkr_conn, "_positions_cache", {}) or {}
                    if pos.symbol in cache:
                        broker_qty = float(cache[pos.symbol])
                    elif self.ibkr_client and self.ibkr_client.isConnected():
                        try:
                            positions = await asyncio.to_thread(self.ibkr_client.positions)
                            reality = {p.contract.symbol: float(p.position) for p in positions}
                            cache.update(reality)
                            if pos.symbol in reality:
                                broker_qty = reality[pos.symbol]
                        except Exception as poll_err:
                            logger.debug(
                                "IBKR reality poll skipped for %s during monitor: %s",
                                pos.symbol,
                                poll_err,
                            )

                pos.meta["broker_flat"] = broker_qty is not None and abs(broker_qty) < 0.1
                if pos.account_type == "ibkr" and pos.meta["broker_flat"]:
                    logger.warning(
                        " MIRROR SYNC: %s memory error (%s) corrected to Broker Reality (0).",
                        pos.symbol,
                        pos.qty,
                    )
                    self._mark_trade_liquidated(pos.symbol, pos.account_type)
                    async with self._state_lock:
                        if pos in self.positions:
                            self.positions.remove(pos)
                    self.closed_positions.append(pos)
                    continue

                # MFE / MAE Tracking
                risk_amt = abs(pos.entry_price - pos.initial_stop)
                if risk_amt < 0.0001:
                    risk_amt = 0.01  # Prevent ZeroDivision

                gross_r = (
                    ((current_price - pos.entry_price) / risk_amt)
                    if pos.qty > 0
                    else ((pos.entry_price - current_price) / risk_amt)
                )
                # Implementation: for LONG, higher gross_r = better (MFE = max).
                # For SHORT, lower gross_r = worse adverse (MAE = max of negatives).
                # gross_r is already sign-correct per direction, so the same
                # max/min assignment is correct for both sides.
                pos.mfe = max(pos.mfe, gross_r)  # best excursion (positive direction)
                pos.mae = min(pos.mae, gross_r)  # worst adverse (negative direction)

                is_short = pos.qty < 0
                price_favourable = (current_price > pos.entry_price and not is_short) or (
                    current_price < pos.entry_price and is_short
                )
                price_adverse = (current_price < pos.entry_price and not is_short) or (
                    current_price > pos.entry_price and is_short
                )
                # Enhancement: Slower, more symmetric belief decay to prevent premature exits.
                # Previous: favorable ×1.01, adverse ×0.98 (asymmetric, too aggressive).
                # New: favorable ×1.005, adverse ×0.995 (slower, symmetric).
                # This gives scalp patterns more time to develop before belief collapse.
                if price_favourable:
                    pos.current_belief = min(pos.current_belief * 1.005, 0.99)
                elif price_adverse:
                    pos.current_belief = max(pos.current_belief * 0.995, 0.01)

                # Build dictionaries for Exit Intelligence Engine
                pos_dict = {
                    "symbol": pos.symbol,
                    "side": "long" if pos.qty > 0 else "short",
                    "quantity": abs(pos.qty),
                    "entry_price": pos.entry_price,
                    "stop_loss": pos.stop_loss,
                    "initial_stop": pos.initial_stop,
                    "bayesian_belief": pos.current_belief,
                    "initial_belief": pos.initial_belief,
                    "mfe_r": pos.mfe,
                    "runner_active": getattr(pos, "runner_active", False),
                }
                market_dict = {
                    "price": current_price,
                    "vix": vix,
                    "vix_baseline": 15.0,
                }
                # Use pre-fetched values (computed once per cycle above)
                if pos.account_type == "mt5":
                    account_dict = {"equity": _mt5_equity, "daily_pnl": _mt5_daily_pnl}
                else:
                    account_dict = {"equity": _ibkr_equity, "daily_pnl": _ibkr_daily_pnl}

                # Perform a 500ms 'Heartbeat Re-vet' using Mind_Ultrathink
                # This checks if the reasons we entered the trade are still valid.
                # Gate: skip stop-breach vetoes for positions under 60s to avoid
                # ghost-stop exits from stale first-tick prices after fill.
                _pos_age_s = (datetime.now(timezone.utc) - _safe_entry_time(pos.entry_time)).total_seconds()
                thought_dna = await self.mind_ultrathink.heartbeat_vet(pos_dict, market_dict)
                if thought_dna.get("veto"):
                    _veto_reason = thought_dna.get("reason", "")
                    # Allow VIX panic and belief-collapse vetoes immediately.
                    # Suppress stop-breach vetoes on positions under 60s (first-tick noise).
                    _is_stop_breach = "stop breached" in _veto_reason.lower()
                    if _is_stop_breach and _pos_age_s < 60:
                        logger.debug(
                            "HEARTBEAT VETO suppressed for %s (age=%.0fs < 60s): %s",
                            pos.symbol, _pos_age_s, _veto_reason,
                        )
                    else:
                        logger.warning(
                            f" Sovereign HEARTBEAT VETO: {pos.symbol} — {_veto_reason}"
                        )
                        exits_triggered.append((pos, "HEARTBEAT_VETO", current_price))
                        continue  # Skip further monitoring for this tick

                # Dynamic Stop Adjustment from Thought DNA (Beta Gate)
                if thought_dna.get("new_stop"):
                    new_stop = float(thought_dna["new_stop"])
                    # Guard: only apply if it tightens (raises for long, lowers for short)
                    if (not is_short and new_stop > pos.stop_loss) or (is_short and new_stop < pos.stop_loss):
                        pos.stop_loss = new_stop

                # 7-level priority evaluation (Standard Engine)
                decision = self.exit_engine.evaluate(
                    pos_dict, market_dict, account_dict, self._oracle_dhatu
                )

                if decision.action == ExitAction.EXIT:
                    logger.info(f"EXIT P{decision.priority}: {pos.symbol} — {decision.reason}")
                    # Gate is now set inside _process_exit to prevent race conditions
                    exits_triggered.append((pos, f"EXIT_P{decision.priority}", current_price))

                elif decision.action == ExitAction.PARTIAL:
                    if not getattr(pos, "runner_active", False):
                        logger.info(f"PARTIAL (Runner Setup): {pos.symbol} at {current_price}")
                        exits_triggered.append((pos, "PARTIAL", current_price))

                elif decision.action == ExitAction.TIGHTEN:
                    if decision.new_stop is not None:
                        old_stop = pos.stop_loss
                        pos.stop_loss = decision.new_stop

                        # Only log if the position actually still exists in reality
                        if not pos.meta.get("broker_flat", False):
                            logger.info(
                                f"TIGHTEN: {pos.symbol} stop ${old_stop:.2f} -> "
                                f"${pos.stop_loss:.2f}"
                            )
                        else:
                            logger.debug(
                                f"Sovereign [Quiet-Sync]: Tightened phantom stop for "
                                f"{pos.symbol} (Flat)."
                            )

                elif decision.action == ExitAction.CASCADE:
                    logger.warning(f"CASCADE: {pos.symbol} — correlated exits detected")
                    exits_triggered.append((pos, "CASCADE", current_price))

                elif decision.action == ExitAction.EVALUATE:
                    logger.info(f"EVALUATE: {pos.symbol} — {decision.reason}")

                elif decision.action == ExitAction.HOLD:
                    if self.bus:
                        await self.bus.publish(
                            "exit.skipped",
                            {
                                "symbol": pos.symbol,
                                "reason": decision.reason,
                                "timestamp": time.time_ns(),
                            },
                        )

                # VIX intraday protocol check
                vix_action = self.vix_protocol.monitor_intraday(vix, vix, vix)
                # Publish calibration.update so Brain can tune thresholds live
                if vix_action == "CLOSE at market":
                    logger.warning(f"VIX PROTOCOL: Close {pos.symbol} immediately")
                    exits_triggered.append((pos, "VIX_PROTOCOL", current_price))

            except Exception as e:
                logger.error(f"Error monitoring {pos.symbol}: {e}")

        # Process exits
        for pos, exit_type, exit_price in exits_triggered:
            # Flag as triggered immediately to block the next tick from spamming
            pos.meta["exit_triggered"] = True
            await self._process_exit(pos, exit_type, exit_price)

        if not self.positions:
            async with self._state_lock:
                self.state = TradingState.SCANNING

    # Legacy _process_exit (RE-REMOVED for System Integrity).
    # This block was re-poisoning the session file with dict-based serialization.

    # STATE: EXIT

    async def _state_exit(self) -> None:
        """Cleanup after exits and feed Agent D."""
        logger.debug("PROCESSING exits and feeding Agent D calibration pipeline")

        # Agent D learning happens in _process_exit
        async with self._state_lock:
            self.state = TradingState.SCANNING
        await asyncio.sleep(1)

    # COGNITIVE TOOLS (Execution-Brain tools for the Minds)

    async def _tool_get_account_status(self, account_type: str = "ibkr") -> dict[str, Any]:
        """Provides the Master Mind (Evolution) with the real-time equity curve."""
        logger.debug(f"MindBridge: Fetching account health for {account_type}...")
        equity = await self._get_account_value(account_type)
        daily_pnl = await self._get_daily_pnl(account_type)

        unrealized_pnl = 0.0
        if account_type == "ibkr" and self.ibkr_client and self.ibkr_client.isConnected():
            acc_vals = self.ibkr_client.accountValues()
            unrealized_pnl = next(
                (float(x.value) for x in acc_vals if x.tag == "UnrealizedPnL"), 0.0
            )

        return {
            "equity": equity,
            "daily_pnl": daily_pnl,
            "unrealized_pnl": unrealized_pnl,
            "peak_equity": self.ibkr_drawdown.peak_equity
            if account_type == "ibkr"
            else self.prop_drawdown.peak_equity,
            "status": "OK" if not self.emergency_halted else "HALTED",
        }

    async def _tool_get_open_positions(self) -> dict[str, Any]:
        """Provides the Healer Mind (Architect) with the live positional context."""
        async with self._state_lock:
            pos_data = []
            for p in self.positions:
                pos_data.append(
                    {
                        "symbol": p.symbol,
                        "qty": p.qty,
                        "unrealized_pnl": p.unrealized_pnl,
                        "belief": p.current_belief,
                    }
                )
        return {"positions": pos_data, "count": len(pos_data)}

    # INTERNAL HELPERS

    async def _handle_emergency(self) -> None:
        """Emergency flatten procedure — flatten all positions."""
        logger.critical("EMERGENCY HALT — Attempting to flatten ALL positions")

        from telegram_alerts import send_telegram_alert

        await send_telegram_alert(
            " *EMERGENCY HALT* \nAttempting to flatten ALL positions due to critical system error."
        )

        for pos in list(self.positions):  # type: ignore
            try:
                if pos.account_type == "ibkr" and self.ibkr_client:
                    logger.warning(f"Emergency flatten {pos.symbol} on IBKR")
                    await self._place_ibkr_order(pos.symbol, "SELL", int(pos.qty))
                elif pos.account_type == "mt5" and self.mt5_conn:
                    logger.warning(f"Emergency flatten {pos.symbol} on MT5")
                    ticket_str = str(pos.trade_id).replace("RESTORED-", "")
                    try:
                        ticket = int(ticket_str)
                        await asyncio.to_thread(self.mt5_conn.close_position, ticket)
                    except ValueError:
                        logger.error(
                            f"MT5: Emergency flatten failed for {pos.symbol} (Invalid Ticket)"
                        )
            except Exception as e:
                logger.error(f"Failed to flatten {pos.symbol}: {e}")

        async with self._state_lock:
            self.positions.clear()
            self.state = TradingState.STANDBY
        await asyncio.sleep(30)

    # EXIT PROCESSING

    async def _confirm_ibkr_order_filled(
        self,
        order_id: int | str,
        symbol: str,
        timeout_seconds: float = 4.0,
    ) -> bool:
        """Confirm an IBKR order filled before mutating realized position state."""
        try:
            target_order_id = int(order_id)
        except (TypeError, ValueError):
            return False

        deadline = time.monotonic() + timeout_seconds
        last_status = "UNKNOWN"
        while time.monotonic() < deadline:
            try:
                for trade in self.ibkr_client.trades():
                    if getattr(trade.order, "orderId", None) != target_order_id:
                        continue
                    last_status = getattr(trade.orderStatus, "status", "UNKNOWN")
                    filled = float(getattr(trade.orderStatus, "filled", 0.0) or 0.0)
                    remaining = float(getattr(trade.orderStatus, "remaining", 0.0) or 0.0)
                    if last_status == "Filled" or (filled > 0 and remaining <= 0):
                        return True
                    if last_status in {"Cancelled", "Inactive"}:
                        logger.warning(
                            "IBKR EXIT NOT FILLED [%s]: order #%s ended as %s.",
                            symbol,
                            target_order_id,
                            last_status,
                        )
                        return False
            except Exception as exc:
                logger.debug("IBKR fill confirmation skipped for %s #%s: %s", symbol, target_order_id, exc)
            await asyncio.sleep(0.25)

        logger.info(
            "IBKR EXIT PENDING [%s]: order #%s not filled yet (last status=%s). "
            "Memory and Telegram realization deferred.",
            symbol,
            target_order_id,
            last_status,
        )
        return False

    async def _process_exit(self, pos: Position, exit_type: str, exit_price: float) -> None:
        """Standardized Exit Resolver (Pillar 5 Upgrade)."""
        try:
            symbol = pos.symbol
            now = datetime.now(timezone.utc)

            # SOVEREIGN BYPASS: Always allow emergency exits (STOP, VETO, VIX, SAFETY)
            # regardless of age or cooldown to prevent account damage during volatility.
            is_emergency = any(
                term in exit_type.upper() for term in ["STOP", "VIX", "VETO", "SAFETY"]
            )

            # Skip exit processing if broker is currently offline.
            # This prevents 3-strike lockouts caused by temporary connection blips.
            broker_online = False
            if self.mode == "paper":
                broker_online = True
            elif pos.account_type == "ibkr":
                broker_online = self._broker_is_connected(self.ibkr_conn)
            elif pos.account_type == "mt5":
                broker_online = self._broker_is_connected(self.mt5_conn)

            if not broker_online:
                logger.warning(
                    f"DELAYED EXIT [{symbol}]: {pos.account_type} is OFFLINE. Postponing pulse."
                )
                return

            if (
                exit_type == "PARTIAL"
                and pos.account_type == "ibkr"
                and hasattr(self, "_is_market_open")
                and not self._is_market_open()
            ):
                logger.info(
                    "PARTIAL DEFERRED [%s]: US equity market is closed; "
                    "keeping memory unchanged until a live fillable session.",
                    symbol,
                )
                return

            # Strike-3 Lockout check
            strikes = self._exit_failure_count.get(symbol, 0)
            if strikes >= 3:
                logger.critical(
                    f"STRIKE-3 LOCKOUT: {symbol} has 3 failed exit attempts. "
                    "Automated execution HALTED to prevent account damage. "
                    "HUMAN INTERVENTION REQUIRED."
                )
                return

            # Cooldown Dampener (10s)
            last_attempt = self._exit_last_attempt.get(
                symbol, datetime(1970, 1, 1, tzinfo=timezone.utc)
            )
            if (now - last_attempt).total_seconds() < 10 and not is_emergency:
                logger.warning(
                    f"DAMPENER ACTIVE: {symbol} exit attempt suppressed. "
                    f"Waiting for cooldown (Last try: {last_attempt.strftime('%H:%M:%S')})."
                )
                return

            # Prevent "Wash Trades" by enforcing a 15-minute minimum hold time
            # unless it is an emergency or hard-stop hit.
            # Guard: ensure entry_time is timezone-aware before subtraction
            entry_time = _safe_entry_time(pos.entry_time)
            age_seconds = (now - entry_time).total_seconds()

            # (Emergency bypass logic handled at top)

            if age_seconds < 100 and not is_emergency:
                logger.warning(
                    f" EXIT IMMUNITY: Rejecting {exit_type} exit for {symbol}. "
                    f"Position is only {age_seconds:.0f}s old. Minimum hold: 100s."
                )
                return

            # Keep track of this attempt
            self._exit_last_attempt[symbol] = now

            # 1. Physical Exit (Broker Handshake)
            # Capture direction sign before any async work that might flip pos.qty
            entry_direction_sign = 1 if pos.qty > 0 else -1
            direction = "SELL" if pos.qty > 0 else "BUY"

            # Handling Partials
            if exit_type == "PARTIAL":
                exit_shares = max(1, abs(int(pos.qty * 0.5)))
            else:
                exit_shares = abs(int(pos.qty))

            if exit_shares == 0:
                logger.warning(f" SKIPPING EXIT for {symbol}: Position size is already 0.")
                if pos in self.positions:
                    self.positions.remove(pos)
                self._mark_trade_liquidated(symbol, pos.account_type)
                return

            # Check if we already have an active order for this symbol at the broker.
            # allow the Brain to re-submit as a fresh Market Order on this tick.
            if self.ibkr_client and pos.account_type == "ibkr":
                active_trades = [
                    t
                    for t in self.ibkr_client.trades()
                    if t.contract.symbol == pos.symbol and not t.isDone()
                ]
                if active_trades:
                    # Check staleness — if order is >45 seconds old, cancel and re-submit
                    STALE_THRESHOLD_SEC = 45
                    stale_found = False
                    for stale_trade in active_trades:
                        order_id = stale_trade.order.orderId
                        submitted_at = self._order_submit_times.get(order_id, now)
                        age_sec = (now - submitted_at).total_seconds()
                        if age_sec > STALE_THRESHOLD_SEC:
                            logger.warning(
                                f" STALE ORDER ESCALATION: {pos.symbol} order #{order_id} "
                                f"is {age_sec:.0f}s old without fill. "
                                "Cancelling and re-submitting as MKT."
                            )
                            try:
                                self.ibkr_client.cancelOrder(stale_trade.order)
                                self._order_submit_times.pop(order_id, None)
                            except Exception as cancel_err:
                                logger.warning(
                                    f"Cancel failed for {pos.symbol} #{order_id}: {cancel_err}"
                                )
                            stale_found = True
                    if not stale_found:
                        logger.warning(
                            f" ORDER SHIELD: Suppressing {exit_type} for {pos.symbol}. "
                            "Active order already exists."
                        )
                        return
                    # else: stale order cancelled — fall through to re-submit below

            logger.warning(
                f"EXECUTING {exit_type} FOR {pos.symbol} | "
                f"PRICE: ${exit_price:.2f} (Attempt: {strikes + 1})"
            )

            order_result = "SUCCESS"  # Default for paper mode or simulations
            if exit_shares > 0 and self.mode != "paper":
                if pos.account_type == "ibkr":
                    # Use 'EMERGENCY' urgency for VETOs to force true Market Orders
                    urg_level = (
                        "EMERGENCY" if "VETO" in exit_type or "FLATTEN" in exit_type else "HIGH"
                    )
                    order_result = await self._place_ibkr_order(
                        pos.symbol,
                        direction,
                        exit_shares,
                        urgency=urg_level,
                        limit_price=exit_price,
                    )
                    if order_result in [None, "SHIELDED"]:
                        logger.info(
                            f" EXIT SUSPENDED [{symbol}]: Broker order was {order_result}. "
                            "Retaining position in memory."
                        )
                        return
                    if not await self._confirm_ibkr_order_filled(order_result, symbol):
                        return

                elif pos.account_type == "mt5" and self.mt5_conn:
                    logger.warning(f"EXECUTING MT5 EXIT FOR {pos.symbol} (Ticket: {pos.trade_id})")
                    ticket_str = str(pos.trade_id).replace("RESTORED-", "")
                    try:
                        ticket = int(ticket_str)
                        success = await asyncio.to_thread(self.mt5_conn.close_position, ticket)
                        if not success:
                            logger.error(
                                f"MT5: Failed to close ticket {ticket}. Retaining position."
                            )
                            return
                    except ValueError:
                        logger.error(
                            f"MT5: Failed to parse ticket ID from '{pos.trade_id}' for {pos.symbol}"
                        )
                        return

            # 2. Mathematical Reflection
            slice_qty = exit_shares if pos.qty > 0 else -exit_shares
            # Removed redundant expression
            # Use entry_direction_sign (captured before async ops) to avoid sign flip
            # from IBKR callbacks modifying pos.qty during execution.
            r_multiple = (
                ((exit_price - pos.entry_price) / abs(pos.entry_price - pos.stop_loss))
                * entry_direction_sign
                if abs(pos.entry_price - pos.stop_loss) > 0
                else 0
            )

            intended_price = getattr(pos, "target", exit_price)
            slippage_pct = abs(exit_price - intended_price) / max(intended_price, 0.01)
            is_dirty = slippage_pct > 0.005  # 50bps threshold
            if is_dirty:
                logger.warning(
                    f"SLIPPAGE DETECTED: {pos.symbol} fill deviated {slippage_pct:.2%} "
                    "from target. Trade marked as DIRTY."
                )

            commission_cost = max(2.0, exit_shares * 0.005)
            vol_multiplier = 1.0 + (exit_shares / 2000.0)
            slippage_penalty = exit_price * 0.0005 * vol_multiplier
            adjusted_exit_price = (
                exit_price - slippage_penalty if slice_qty > 0 else exit_price + slippage_penalty
            )

            from decimal import Decimal

            d_exit = Decimal(str(adjusted_exit_price))
            d_entry = Decimal(str(pos.entry_price))
            d_qty = Decimal(str(slice_qty))
            d_comm = Decimal(str(commission_cost))
            d_slip = Decimal(str(pos.slippage_cost))
            d_total_qty = Decimal(str(abs(pos.qty) or 1))

            realized_net_pnl = float(
                (d_exit - d_entry) * d_qty
                - d_comm
                - (d_slip * (Decimal(str(exit_shares)) / d_total_qty))
            )

            # 3. Virtual Reflection (Wisdom & Skills)
            self.session_pnl += realized_net_pnl
            if exit_type != "PARTIAL":
                await self._log_trade_exit(
                    pos, exit_type, adjusted_exit_price, realized_net_pnl, r_multiple
                )

            # 4. Neural Cleanup & Learning
            if exit_type == "PARTIAL":
                old_qty = abs(pos.qty)
                if pos.qty > 0:
                    pos.qty -= exit_shares
                else:
                    pos.qty += exit_shares
                pos.runner_active = True
                pos.shares_remaining = abs(pos.qty) / old_qty if old_qty > 0 else 0.0
            else:
                if self.mode == "paper":
                    async with self._state_lock:
                        if pos in self.positions:
                            self.positions.remove(pos)
                    self.closed_positions.append(pos)

                PORTFOLIO_ANALYZER.record_close(
                    symbol=pos.symbol,
                    side="LONG" if pos.qty > 0 else "SHORT",
                    quantity=abs(pos.qty),
                    entry_price=pos.entry_price,
                    exit_price=adjusted_exit_price,
                    pnl_usd=realized_net_pnl,
                    ts_entry=pos.entry_time,
                    ts_exit=now,
                )

                try:
                    LEDGER.record_exit(
                        symbol=pos.symbol,
                        exit_type=exit_type,
                        pnl_usd=realized_net_pnl,
                        r_multiple=r_multiple,
                        triggered_by="exit_intelligence",
                        agent_votes={"exit_intelligence": exit_type},
                        override="DIRTY_FILL" if is_dirty else "",
                        meta={
                            "entry_price": pos.entry_price,
                            "exit_price": adjusted_exit_price,
                            "slippage_pct": round(slippage_pct, 5),
                            "regime": self.current_regime,
                            "pattern": pos.pattern or "",
                        },
                    )
                except Exception as _le:
                    logger.error(f"DecisionLedger exit record FAILED for {pos.symbol}: {_le}")

                # Reset failure count on successful full exit
                self._exit_failure_count[symbol] = 0

                if not hasattr(self, "_loss_streak"):
                    self._loss_streak = 0

                # Guard: Do NOT count ghost (0-unit) or broker-veto exits as loss streaks.
                # These are infrastructure events, not real trading failures. Counting them
                # would prematurely trigger ABHAVA lockdown based on phantom data.
                _is_ghost_loss = abs(exit_shares) < 0.0001
                _is_veto_exit = exit_type in ("HEARTBEAT_VETO", "LIQUIDATED")
                _is_countable_loss = not _is_ghost_loss and not _is_veto_exit

                if realized_net_pnl < 0 and _is_countable_loss:
                    self._loss_streak += 1
                    if self._loss_streak >= 5:
                        logger.critical(
                            f" LOSS STREAK DETECTED ({self._loss_streak}). "
                            "TRIGGERING RISK-OFF REGIME."
                        )
                        self.current_regime = "RISK_OFF"
                        # Reset streak after triggering so we can eventually recover
                        self._loss_streak = 0
                elif realized_net_pnl >= 0 or not _is_countable_loss:
                    self._loss_streak = 0

            if hasattr(self, "recursive_evolution"):
                self.recursive_evolution.evolve_live(
                    pattern_name=pos.pattern or pos.meta.get("pattern", "UNKNOWN"),
                    pnl=realized_net_pnl,
                    regime=self.current_regime,
                    shares_remaining=getattr(pos, "shares_remaining", 0.0),
                )

            if self.bus:
                await self.bus.publish(
                    "trade.exit",
                    {
                        "symbol": pos.symbol,
                        "pnl": realized_net_pnl,
                        "exit_type": exit_type,
                        "is_dirty": is_dirty,
                        "pattern": pos.pattern or pos.meta.get("pattern", "UNKNOWN"),
                        "regime": self.current_regime,
                        "r_multiple": r_multiple,
                        "shares_remaining": getattr(pos, "shares_remaining", 0.0),
                    },
                )

            # Telegram Alert (Enhanced for Sovereign Elite v2)
            from telegram_alerts import send_telegram_alert

            # Smart Metadata Recovery
            icon = "💰" if realized_net_pnl > 0 else "📉" if realized_net_pnl < 0 else "🛡️"
            intent = pos.meta.get("intent") or getattr(pos, "intent", "Sovereign")
            pattern_name = pos.meta.get("pattern") or pos.pattern or "Sovereign Signal"

            # Account ID Sanitization
            acc_id = pos.account_id
            if acc_id == "UNKNOWN":
                from config import IBKR_ACCOUNT_ID

                acc_id = IBKR_ACCOUNT_ID or "Master Account"

            # Reason Translation
            reason = exit_type.replace("_", " ").title()
            if "HEARTBEAT" in reason.upper():
                reason = "Sovereign Safety Veto"

            # Duration Formatting
            duration_min = (now - _safe_entry_time(pos.entry_time)).total_seconds() / 60
            duration_str = (
                f"{duration_min:.1f}m" if duration_min < 60 else f"{duration_min / 60:.1f}h"
            )

            # Enhancement: Store original quantity before position removal to prevent "0 units" in alerts
            original_qty = abs(pos.qty) if abs(pos.qty) > 0.0001 else 1.0

            # Format detailed message
            title = "PARTIAL HARVEST" if exit_type == "PARTIAL" else "TRADE FINALIZED"
            outcome = (
                "PROFIT"
                if realized_net_pnl > 0
                else "LOSS"
                if realized_net_pnl < 0
                else "BREAKEVEN"
            )

            msg = (
                f"{icon} <b>{title}: {pos.symbol}</b>\n"
                f"<i>Account: {acc_id} ({pos.account_type.upper()})</i>\n"
                "───────────────────\n"
                f"<b>Size:</b> {original_qty:.0f} units\n"
                f"<b>Entry:</b> ${pos.entry_price:,.2f}\n"
                f"<b>Exit:</b>  ${pos.current_price:,.2f}\n"
                "───────────────────\n"
                f"<b>Strategy:</b> {intent}\n"
                f"<b>Pattern:</b> {pattern_name}\n"
                f"<b>Reason:</b> {reason}\n"
                "───────────────────\n"
                f"<b>Outcome:</b> {outcome}\n"
                f"<b>Net PnL:</b> <code>${realized_net_pnl:+.2f}</code>\n"
                f"<b>Efficiency:</b> {r_multiple:+.2f}R\n"
                f"<b>Duration:</b> {duration_str}\n"
                "───────────────────\n"
                f"<b>SESSION P&L:</b> <code>${self.session_pnl:+.2f}</code>"
            )
            try:
                await send_telegram_alert(msg)
            except Exception as tg_err:
                logger.warning(f"Telegram alert failed for {pos.symbol} exit: {tg_err}")

        except Exception as e:
            logger.error(f"Failed to process exit for {pos.symbol}: {e}")
            self._exit_failure_count[symbol] = strikes + 1

    # HELPER METHODS
