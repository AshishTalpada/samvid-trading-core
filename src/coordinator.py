import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

import numpy as np
import pandas as pd
from dateutil import parser as dtparser

from resilience_layer import ApexExoskeleton

if TYPE_CHECKING:
    from brain import TradingBrain
    from mind_bridge import MindBridge

from agent_a import agent_a_validate_trade
from backtest_validator import BacktestValidator
from decision_ledger import LEDGER
from execution.slippage import SlippageModel
from telegram_alerts import send_telegram_alert

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 3
# NOTE: asyncio.Semaphore is created lazily inside the class to avoid
# attaching to the wrong event loop when imported at module level.


class TradingCoordinator:
    """
    Equipped with Concurrent Task-Graphing (Pillar 3), Adaptive Thinking (Pillar 5),
    and Autonomy Skill Permissioning (Pillar 6).
    """

    _neural_semaphore_obj: asyncio.Semaphore | None = None

    @classmethod
    def get_neural_semaphore(cls) -> asyncio.Semaphore:
        """Lazy-initializes the semaphore to ensure it binds to the running event loop."""
        if cls._neural_semaphore_obj is None:
            cls._neural_semaphore_obj = asyncio.Semaphore(1)
        return cls._neural_semaphore_obj

    def __init__(self, bridge: "MindBridge", brain: "TradingBrain") -> None:
        self.bridge = bridge
        self.brain = brain
        self._pending_vets = set()
        self.exoskeleton = ApexExoskeleton(brain)
        self._semaphore: asyncio.Semaphore | None = None  # Lazy-init to bind to running loop
        self.slippage_model = SlippageModel()
        try:
            from cognitive_diversity import CognitiveDiversityEnforcer
            self._diversity_enforcer = CognitiveDiversityEnforcer()
        except Exception:
            self._diversity_enforcer = None
        try:
            from ensemble_distill import EnsembleDistiller
            self._ensemble_distiller = EnsembleDistiller()
        except Exception:
            self._ensemble_distiller = None
        try:
            from reflexivity_scale import ReflexivityScale
            self._reflexivity = ReflexivityScale(lookback=20)
        except Exception:
            self._reflexivity = None
        try:
            from game_theory import GameTheoryPositionSizer
            self._game_theory_sizer = GameTheoryPositionSizer()
        except Exception:
            self._game_theory_sizer = None

    def _estimate_entry_friction_per_share(
        self,
        *,
        entry_price: float,
        shares: int,
        spread_data: dict[str, Any] | None,
    ) -> float:
        """Estimate per-share entry friction using spread plus modeled slippage."""
        entry_price = float(entry_price or 0.0)
        shares = max(1, int(shares or 1))
        spread_data = spread_data or {}
        spread = max(0.0, float(spread_data.get("spread", 0.0) or 0.0))
        if entry_price <= 0:
            return spread

        order_notional = entry_price * shares
        bid = float(spread_data.get("bid", 0.0) or 0.0)
        ask = float(spread_data.get("ask", 0.0) or 0.0)
        top_liquidity = float(
            spread_data.get("top_liquidity")
            or spread_data.get("book_liquidity_at_price")
            or 0.0
        )
        if top_liquidity <= 0 and bid > 0 and ask > 0:
            # Conservative fallback: assume only the estimated order notional is visible
            # at top of book when no L2 size is provided.
            top_liquidity = order_notional

        spread_pct = spread / entry_price
        slippage_pct = self.slippage_model.predict_slippage(
            order_notional,
            spread_pct,
            top_liquidity,
        )
        # predict_slippage() bundles half the bid/ask spread into its result. The caller
        # already adds the full `spread` below, so strip the half-spread component here to
        # avoid double-counting it (which over-inflates friction by ~1.5x the spread).
        impact_pct = max(0.0, slippage_pct - (spread_pct / 2.0))
        return spread + (entry_price * impact_pct)

    def _has_fresh_realtime_entry_tick(self, symbol: str) -> bool:
        """Use the realtime tick cache as entry proof when OHLCV bars are delayed."""
        data_pipeline = getattr(self.brain, "data_pipeline", None)
        get_last_price = getattr(data_pipeline, "get_last_price", None)
        if not callable(get_last_price):
            return False
        try:
            price = get_last_price(symbol.upper())
        except Exception as exc:
            logger.warning(
                "Coordinator: realtime entry tick proof lookup failed for %s: %s",
                symbol,
                exc,
            )
            return False
        try:
            return float(price or 0.0) > 0.0
        except (TypeError, ValueError):
            return False

    def _entry_data_block_reason(self, symbol: str) -> str | None:
        """Return a fail-closed reason when live entry data proof is missing or expired."""
        if str(getattr(self.brain, "mode", "paper")).lower() == "paper":
            return None
        if os.environ.get("SOVEREIGN_ALLOW_UNVERIFIED_ENTRY_DATA") == "1":
            return None

        freshness_proofs = getattr(self.brain, "_last_fresh_bar_at", {})
        if not isinstance(freshness_proofs, dict):
            return "verified bar freshness store unavailable"
        verified_at = freshness_proofs.get(symbol.upper())
        if verified_at is None:
            if self._has_fresh_realtime_entry_tick(symbol):
                return None
            return "no verified fresh bar available"

        try:
            max_age = float(os.environ.get("SOVEREIGN_ENTRY_DATA_PROOF_MAX_AGE_SEC", "30"))
        except ValueError:
            max_age = 30.0
        max_age = max(5.0, min(max_age, 300.0))
        proof_age = time.monotonic() - float(verified_at)
        if proof_age > max_age:
            if self._has_fresh_realtime_entry_tick(symbol):
                return None
            return f"verified bar freshness proof expired ({proof_age:.1f}s > {max_age:.1f}s)"
        return None

    def _format_execution_alert(
        self,
        *,
        symbol: str,
        order_id: Any,
        pattern: Any,
        order_side: str,
        intent: str,
        shares: int,
        quorum_count: int,
        decision: dict[str, Any],
        task_id: str,
    ) -> str:
        """Build the operator Telegram alert after broker acceptance."""
        side_str = "LONG" if order_side == "BUY" else "SHORT"
        full_intent = f"{side_str} {intent}"
        mode = str(getattr(self.brain, "mode", "UNKNOWN")).upper()
        broker = str(getattr(self.brain, "active_broker", "UNKNOWN")).upper()
        pattern_name = str(getattr(pattern, "name", "UNKNOWN") or "UNKNOWN")
        category = str(getattr(pattern, "category", intent) or intent)
        confidence = float(decision.get("confidence", 0.0) or 0.0) * 100.0
        exploration = "YES" if decision.get("paper_exploration") else "NO"
        reason = str(decision.get("reason", "Approved by coordinator"))[:220]
        rr = float(getattr(pattern, "r_r_ratio", 0.0) or 0.0)
        return (
            f"[EXECUTION] <b>{symbol}</b> broker order accepted\n"
            f"<b>Mode:</b> <code>{mode}</code>\n"
            f"<b>Broker:</b> {broker}\n"
            f"<b>Order ID:</b> <code>{order_id}</code>\n"
            f"<b>Side / Method:</b> {full_intent}\n"
            f"<b>Pattern:</b> {pattern_name}\n"
            f"<b>Setup Class:</b> {category}\n"
            f"<b>Price:</b> ${float(getattr(pattern, 'entry', 0.0) or 0.0):.2f}\n"
            f"<b>Qty:</b> {shares}\n"
            f"<b>Stop:</b> ${float(getattr(pattern, 'stop', 0.0) or 0.0):.2f}\n"
            f"<b>Target:</b> ${float(getattr(pattern, 'target', 0.0) or 0.0):.2f}\n"
            f"<b>Net R:R:</b> {rr:.2f}\n"
            f"<b>Confidence:</b> {confidence:.1f}%\n"
            f"<b>Paper Exploration:</b> {exploration}\n"
            f"<b>Quorum:</b> {quorum_count} agents\n"
            f"<b>Task:</b> <code>{task_id}</code>\n"
            f"<b>Reason:</b> {reason}"
        )

    def _finalize_open_task(self, task: Any, phase: str, reason: str) -> None:
        """Close a spawned task when a pre-vetting guard returns early."""
        if not task:
            return
        status = getattr(getattr(task, "status", None), "value", getattr(task, "status", ""))
        if str(status).lower() not in {"pending", "running"}:
            return
        try:
            task.set_phase(phase, reason)
            task.finalize("VETOED")
        except Exception as exc:
            logger.warning("Coordinator: failed to finalize task %s: %s", getattr(task, "id", "?"), exc)

    def _check_best_day_rule(self, today_pnl: float, broker: str) -> tuple[bool, str]:
        """
        FTMO Best Day Rule enforcement (F-spec).
        Today's profit must not exceed 2/3 of the average of other recent profitable days.
        On prop/MT5 track this is a hard veto. On IBKR it is advisory.
        Returns (passes, reason_string).
        """
        from config import FTMO_BEST_DAY_RATIO

        if today_pnl <= 0:
            return True, ""  # Only applies when today is profitable

        cursor = None
        try:
            db_conn = getattr(self.brain, "db_conn", None)
            if db_conn is None:
                return True, ""  # No DB — can't enforce, allow

            cursor = db_conn.cursor()
            # Fetch daily P&L for the last 30 trading days (excluding today)
            from datetime import datetime, timezone

            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cursor.execute(
                """
                SELECT DATE(timestamp) as day, SUM(pnl_dollars) as daily_pnl
                FROM trades
                WHERE DATE(timestamp) < DATE(?) AND broker = ?
                GROUP BY day
                ORDER BY day DESC
                LIMIT 30
                """,
                (today_str, broker.lower()),
            )
            rows = cursor.fetchall()
            other_profitable = [float(r[1]) for r in rows if r[1] is not None and float(r[1]) > 0]
            if not other_profitable:
                return True, ""  # No history to compare against

            avg_others = sum(other_profitable) / len(other_profitable)
            threshold = FTMO_BEST_DAY_RATIO * avg_others  # 2/3 × avg

            if today_pnl > threshold:
                reason = (
                    f"Best Day Rule: today=${today_pnl:.2f} > {FTMO_BEST_DAY_RATIO:.2f}×"
                    f"avg_others=${avg_others:.2f} (threshold=${threshold:.2f})"
                )
                return False, reason
            return True, ""
        except Exception as exc:
            logger.warning("Best Day Rule check failed (non-fatal): %s", exc)
            return True, ""
        finally:
            if cursor is not None:
                cursor.close()

    async def initiate_trade_lifecycle(
        self, symbol: str, proposal: dict[str, Any], is_probe: bool = False
    ) -> bool | None:
        """Starts the multi-phase vetting quorum for a trade proposal."""
        symbol = symbol.upper()
        task = proposal.get("task")

        if self.brain.bus:
            await self.brain.bus.publish(
                "consensus.update",
                {
                    "symbol": symbol,
                    "phase": "EVALUATING",
                    "decision": "VOTING",
                    "votes": [],
                    "timestamp": time.time() * 1000,
                },
            )

        # Enhancement: Hard-block new entries if daily loss already >= 4% (FTMO daily limit).
        # Checked here with unrealized PnL so open losing positions count.
        if not is_probe:
            try:
                account_type = getattr(self.brain, "active_broker", "ibkr").lower()
                daily_pnl_now = await self.brain._get_daily_pnl(account_type)
                account_val = await self.brain.get_safe_buying_power(account_type) or 500.0
                from config import FTMO_DAILY_LIMIT
                if daily_pnl_now < 0 and abs(daily_pnl_now) / max(account_val, 1.0) >= FTMO_DAILY_LIMIT:
                    logger.warning(
                        "Coordinator [%s] DAILY_LOSS_HARD_BLOCK: daily PnL %.2f = %.1f%% >= %.0f%% limit. No new entries.",
                        symbol, daily_pnl_now, abs(daily_pnl_now) / account_val * 100, FTMO_DAILY_LIMIT * 100,
                    )
                    LEDGER.record_veto(symbol=symbol, reason=f"DAILY_LOSS_LIMIT: {daily_pnl_now:.2f}")
                    self._finalize_open_task(task, "DAILY_LOSS_BLOCK", f"daily PnL {daily_pnl_now:.2f}")
                    return False
            except Exception as _dlb_err:
                logger.debug("Daily loss hard-block check failed (non-fatal): %s", _dlb_err)

        # Enhancement: Block new entries in last 30 minutes of RTH (3:30–4:00 PM ET).
        if not is_probe:
            try:
                import datetime as _dt
                from zoneinfo import ZoneInfo
                _now_et = _dt.datetime.now(ZoneInfo("America/New_York"))
                _t = _now_et.time()
                if _dt.time(15, 30) <= _t < _dt.time(16, 0):
                    logger.info(
                        "Coordinator [%s] RTH_CLOSE_GUARD: No new entries in last 30 min of RTH (%s ET).",
                        symbol, _now_et.strftime("%H:%M"),
                    )
                    self._finalize_open_task(task, "RTH_CLOSE_GUARD", _now_et.strftime("%H:%M ET"))
                    return False
            except Exception as _rth_err:
                logger.debug("RTH close guard check failed (non-fatal): %s", _rth_err)

        pattern = proposal.get("pattern")
        if pattern:
            if task:
                task.set_phase("RR_CHECK", symbol)
                task.log(f"PHASE_RR: Analyzing Risk/Reward for {symbol}. Pattern: {pattern.name}")

            # FTMO Best Day Rule enforcement (must precede sizing/RR checks)
            active_broker = getattr(self.brain, "active_broker", "ibkr").lower()
            today_session_pnl = float(getattr(self.brain, "session_pnl", 0.0))
            bdr_passes, bdr_reason = self._check_best_day_rule(today_session_pnl, active_broker)
            if not bdr_passes and not is_probe:
                is_prop = active_broker in ("mt5", "prop")
                if is_prop:
                    logger.warning(f"Coordinator [{symbol}]  BEST_DAY_RULE VETO (prop): {bdr_reason}")
                    LEDGER.record_veto(symbol=symbol, reason=f"BEST_DAY_RULE: {bdr_reason}")
                    self._finalize_open_task(task, "BEST_DAY_RULE", bdr_reason)
                    return False
                else:
                    logger.warning(f"Coordinator [{symbol}]  BEST_DAY_RULE WARNING (ibkr advisory): {bdr_reason}")

            balance = await self.brain.get_safe_buying_power("ibkr")
            from config import COMMISSION_PER_ROUND_TRIP, USD_CAD_RATE

            # Necessary for accurate sizing when trading US assets on a CAD-denominated account.
            # Implementation: negative balance is truthy, so "or 500.0" won't trigger;
            # guard explicitly so negative-equity accounts don't produce inverted share counts
            effective_balance = balance if (balance and balance > 0) else 500.0
            balance_usd = effective_balance / max(USD_CAD_RATE, 0.01)  # guard divide-by-zero

            risk_amt = abs(pattern.entry - pattern.stop)
            reward_amt = abs(pattern.target - pattern.entry)
            # Unified Sizing Calculation
            # We use a more realistic position size estimate for RR calculation.
            # Implementation: guard against zero/negative entry price to prevent ZeroDivisionError
            if not pattern.entry or pattern.entry <= 0:
                logger.warning("Coordinator [%s]: invalid pattern.entry=%s — aborting", symbol, pattern.entry)
                self._finalize_open_task(task, "INVALID_PATTERN", f"entry={pattern.entry}")
                return False
            est_shares = max(1, int(balance_usd * 4.0 * 0.1 / pattern.entry))

            if risk_amt > 0:
                spread_data = await self.brain.get_current_spread(symbol)
                # Implementation: get_current_spread() can return None; guard before calling .get()
                spread_data = spread_data or {}
                spread = self._estimate_entry_friction_per_share(
                    entry_price=pattern.entry,
                    shares=est_shares,
                    spread_data=spread_data,
                )
                comm_per_share = COMMISSION_PER_ROUND_TRIP / est_shares

                total_reward_dollars = reward_amt - spread - comm_per_share
                total_risk_dollars = risk_amt + spread + comm_per_share
                # Implementation: if costs consume the entire reward, reject explicitly with a clear message
                if total_reward_dollars <= 0 and not is_probe:
                    logger.warning(
                        "Coordinator [%s]: trade reward (%.4f) consumed by costs (spread=%.4f "
                        "comm=%.4f). Net reward <= 0 — rejecting.",
                        symbol, reward_amt, spread, comm_per_share,
                    )
                    self._finalize_open_task(task, "FRICTION_VETO", "net reward consumed by costs")
                    return False
                real_rr = total_reward_dollars / total_risk_dollars if total_risk_dollars > 0 else 0

                # On small accounts, the 1.3 Net RR is a 'Mathematical Wall' due to fixed commission.
                is_small_account = (balance or 0) < 2000.0
                dollar_risk = total_risk_dollars * est_shares
                _risk_pct = (dollar_risk / balance_usd) if (balance_usd > 0) else 0.05

                # Friction veto: block trades where net RR (after spread + commission) is too low.
                # Standard institutional threshold is 1.3. Small accounts (<$2k) get 1.0
                # since fixed commissions compress ratio on small size.
                if is_small_account:
                    threshold = 1.0
                    if task:
                        task.log(
                            f"RR_RELAX: Small account detected. Threshold relaxed to {threshold:.2f} (Risk: ${dollar_risk:.2f} USD)."
                        )
                else:
                    threshold = 1.3

                if real_rr < threshold and not is_probe:
                    if task:
                        task.log(
                            f"FRICTION_VETO: Net RR {real_rr:.2f} < {threshold} (S:{spread}, C:{comm_per_share:.3f}). Aborting."
                        )
                    logger.info(
                        f"Coordinator [{symbol}]  FRICTION VETO: Net RR {real_rr:.2f} is < {threshold}."
                    )

                    if self.brain.bus:
                        await self.brain.bus.publish(
                            "consensus.update",
                            {
                                "symbol": symbol,
                                "phase": "FRICTION_VETO",
                                "decision": "REJECT",
                                "reason": f"Net RR {real_rr:.2f} < {threshold}",
                                "votes": [],
                                "timestamp": time.time() * 1000,
                            },
                        )
                    self._finalize_open_task(task, "FRICTION_VETO", f"Net RR {real_rr:.2f} < {threshold}")
                    return False

        # -- IDEMPOTENCY & CORTEX CACHE -------------------
        if symbol in self._pending_vets and not is_probe:
            logger.debug(f"Coordinator: Skipping redundant vet for {symbol} (already in progress).")
            return False

        self._pending_vets.add(symbol)
        try:
            oracle_freeze = bool(getattr(self.brain, "_oracle_freeze", False))
            oracle_modifier = float(getattr(self.brain, "_oracle_risk_modifier", 1.0) or 0.0)
            oracle_dhatu = str(getattr(self.brain, "_oracle_dhatu", "UNKNOWN"))
            if not is_probe and (oracle_freeze or oracle_modifier <= 0.0):
                reason = (
                    f"ORACLE_FREEZE: {oracle_dhatu} "
                    f"(risk_modifier={oracle_modifier:.2f}) blocks new entries."
                )
                logger.warning("Coordinator [%s] %s", symbol, reason)
                if task:
                    task.set_phase("ORACLE_FREEZE", reason)
                    task.finalize("VETOED")
                return False

            if task:
                task.set_phase("VETTING", "checking cache and agent quorum")
            cache = await self.exoskeleton.check_cortex_cache(symbol, proposal["pattern"].entry)
            if cache and not is_probe:
                if task:
                    task.log(f"CORTEX_HIT: Re-using cached consensus for {symbol}.")
                return await self._execute_decision(
                    symbol,
                    cache["decision"],
                    proposal["pattern"],
                    cache["all_votes"],
                    is_probe,
                    cache.get("shares", 0),
                    task=task,
                )

            has_position = any(getattr(p, "symbol", None) == symbol for p in self.brain.positions)
            if has_position and not is_probe:
                if task:
                    task.log(f"REDUNDANCY_VETO: Position already active for {symbol}.")
                    # Transition to KILLED so it doesn't stay 'RUNNING' in TaskManager
                    from sovereign_task import TaskStatus

                    task.transition(TaskStatus.KILLED)
                return False

            if self._semaphore is None:
                self._semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
            async with self._semaphore:

                async def _poll_safe(name, func):
                    """Imperial Dispatcher (Sync -> Thread | Async -> Native)"""
                    try:
                        if asyncio.iscoroutinefunction(func):
                            return await func()
                        # Sync-safe bridge: run in thread pool to prevent blocking the event loop
                        res = await asyncio.to_thread(func)
                        if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                            return await res
                        return res
                    except Exception as poll_err:
                        logger.warning(f"Coordinator: {name} poll failed: {poll_err}")
                        return {
                            "agent": name,
                            "vote": "ABSTAIN",
                            "confidence": 0.0,
                            "reason": f"Fallback abstain: {poll_err}",
                            "timestamp": time.time_ns(),
                        }

                async def _poll_neural_safe(name, func):
                    """Gated Neural Dispatcher with Class-Level Semaphore (Selective VRAM Gating)."""
                    if name == "Native_SLM":
                        async with self.get_neural_semaphore():
                            return await _poll_safe(name, func)
                    return await _poll_safe(name, func)

                proposal_id = str(uuid.uuid4())[:8]
                if task:
                    task.log(f"QUORUM_INIT: Starting 7-Agent Sovereign Audit for {symbol}.")

                if self.brain.bus:
                    await self.brain.bus.publish(
                        "consensus.update",
                        {
                            "symbol": symbol,
                            "phase": "QUORUM_INIT",
                            "decision": "VOTING",
                            "votes": [],
                            "timestamp": time.time() * 1000,
                        },
                    )

                # -- PILLAR 6: SKILL TREE PERMISSIONING -------------------
                if not self.brain.skill_tree.is_unlocked("vetting"):
                    logger.warning(
                        "Coordinator: Skill 'vetting' is LOCKED. Matrix is in Training Mode."
                    )
                    return False

                if self.brain.dms:
                    self.brain.dms.record_heartbeat("COORDINATOR")

                timestamp = time.time_ns()
                account_value = await self.brain.get_safe_buying_power(
                    self.brain.active_broker.lower()
                )

                from config import USD_CAD_RATE

                if account_value > 500000 and symbol not in ["XAUUSD", "US100"]:
                    account_value = account_value / USD_CAD_RATE
                    logger.debug(
                        f"Coordinator: Converted CAD balance to USD for {symbol} sizing: ${account_value:,.2f}"
                    )

                pattern = proposal["pattern"]

                _lambda = proposal.get("lambda")
                if _lambda is None or _lambda <= 0:
                    alpha_val = pattern.confidence / 100.0
                else:
                    alpha_val = _lambda

                # Fetch OHLCV early to support Impact Oracle and Agent A
                ohlcv_1m = await self.brain._fetch_ohlcv(symbol)
                if (
                    ohlcv_1m is None or isinstance(ohlcv_1m, str) or len(ohlcv_1m) < 20
                ) and not is_probe:
                    logger.warning(
                        f"Coordinator [{proposal_id}]  DATA VETO: Insufficient OHLCV for {symbol}."
                    )
                    return False

                # Fetch spread for sizing. get_current_spread() can return None, so
                # fail closed to an empty dict before the sizer subscripts it below.
                spread_data = await self.brain.get_current_spread(symbol) or {}

                # Early Agent D veto gate — avoid sizing cost for statistically doomed trades
                if not is_probe:
                    try:
                        agent_d_early = await asyncio.wait_for(
                            asyncio.to_thread(
                                self.brain.live_learner.evaluate_proposal,
                                pattern.name,
                                self.brain.current_regime,
                                proposal.get("session", "RTH"),
                            ),
                            timeout=5.0,
                        )
                        if agent_d_early.get("vote") == "NO":
                            logger.info(
                                "Coordinator [%s] EARLY_VETO by Agent_D: %s — skipping sizing.",
                                symbol,
                                agent_d_early.get("reason", ""),
                            )
                            return
                    except (asyncio.TimeoutError, Exception) as _early_d_err:
                        logger.debug("Agent D early veto check failed/timed out: %s", _early_d_err)
                        # Non-fatal — fall through to normal path

                # Sizing Calculation for Context
                # For probes: skip the sizer entirely — it will return 0 shares with no live data.
                # A probe is a wiring test, not a real order, so shares=1 is sufficient to pass guards.
                if is_probe:
                    shares = 1
                    pos_value = pattern.entry * 1
                else:
                    ohlcv_for_sizing = (
                        ohlcv_1m
                        if (ohlcv_1m is not None and not isinstance(ohlcv_1m, str))
                        else None
                    )
                    if self.brain.active_broker.upper() == "MT5":
                        risk_per_trade = getattr(self.brain, "mt5_risk_per_trade", 10.0)
                        shares = (
                            self.brain.mt5_sizer.calculate_lots(
                                risk_per_trade, pattern.entry, pattern.stop, symbol
                            )
                            or 0.0
                        )
                        pos_value = shares * 100000.0  # Synthetic estimate for Forex tracking
                    else:
                        sizing = self.brain.ibkr_sizer.calculate(
                            win_prob=alpha_val,
                            r_r_ratio=pattern.r_r_ratio,
                            balance=account_value,
                            account_value=account_value,
                            entry_price=pattern.entry,
                            stop_price=pattern.stop,
                            target_price=pattern.target,
                            spread=float(spread_data.get("spread", 0.0) or 0.0),
                            instrument=symbol,
                            ohlcv_df=ohlcv_for_sizing,
                            regime=self.brain.current_regime,
                            regime_modifier=self.brain.regime_classifier.get_risk_modifier(
                                self.brain.current_regime
                            ),
                            drawdown_modifier=self.brain.ibkr_drawdown.get_size_modifier(),
                            loss_modifier=self.brain.loss_tracker.get_size_modifier(),
                            is_probe=is_probe,
                        )
                        shares = int(sizing.get("step8_shares", 0))
                        pos_value = sizing.get("position_value", 0.0)

                        total_mod = sizing.get("total_multiplier", 1.0)
                        if total_mod < 0.9 and not is_probe:
                            logger.warning(
                                f"Coordinator [{proposal_id}]: Imperial Safety Protocol Active. "
                                f"Size reduced to {total_mod:.1%} of theoretical max (DD/Loss/Regime Guard)."
                            )

                # Enhancement: C: Zero-share veto
                if shares <= 0 and not is_probe:
                    logger.warning(
                        f"Coordinator [{proposal_id}] ZERO-SHARE VETO: Position sizer returned shares=0 for {symbol}."
                    )
                    return False

                shared_context = {
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "pattern": pattern,
                    "regime": self.brain.current_regime,
                    "account_value": account_value,
                    "balance": account_value,  #
                    "is_probe": is_probe,
                    "shares": shares,
                    "new_position_value": pos_value,
                    "proposed_value": pos_value,  #
                    "total_position_value": sum(
                        getattr(p, "qty", 0)
                        * getattr(p, "current_price", getattr(p, "entry_price", 0))
                        for p in self.brain.positions
                    ),
                    "positions": self.brain.positions,
                    "proposal_id": proposal_id,
                    "is_long": pattern.entry > pattern.stop,
                    "vix": await self.brain._get_vix(),
                    "dhatu_state": getattr(self.brain, "_oracle_dhatu", "UNKNOWN"),
                    "oracle_freeze": bool(getattr(self.brain, "_oracle_freeze", False)),
                    "oracle_risk_modifier": float(
                        getattr(self.brain, "_oracle_risk_modifier", 1.0) or 0.0
                    ),
                    "potential_profit": abs(pattern.target - pattern.entry),
                    "commission": max(COMMISSION_PER_ROUND_TRIP, (shares or 1) * 0.01),
                }

                # Probes use synthetic geometry — skip data-quality vetoes for wiring tests
                if not is_probe:
                    math_val = await self.brain.mind_math._tool_validate_geometry(
                        direction=("LONG" if shared_context["is_long"] else "SHORT"),
                        entry_price=pattern.entry,
                        stop_price=pattern.stop,
                        target_price=pattern.target,
                        atr=getattr(pattern, "atr", 0.0),
                    )
                    if not math_val["valid"]:
                        logger.warning(
                            f"Coordinator [{proposal_id}]  MATH VETO: {math_val['reason']}"
                        )
                        return False

                try:
                    if not is_probe:
                        ohlcv_data = await self.brain._fetch_ohlcv(symbol)
                        if ohlcv_data is not None and not isinstance(ohlcv_data, str):
                            q_prices = ohlcv_data["close"].to_numpy()
                            q_volumes = ohlcv_data["volume"].to_numpy()
                            q_side = "LONG" if shared_context["is_long"] else "SHORT"
                            q_gate = await self.brain.quant_gate(
                                symbol,
                                q_side,
                                {
                                    "prices": q_prices,
                                    "volumes": q_volumes,
                                    "vix": shared_context["vix"],
                                },
                            )
                            if not q_gate["approved"]:
                                logger.info(
                                    f"Coordinator [{proposal_id}]  QUANT VETO: {q_gate['reason']}"
                                )
                                return False
                except Exception as qe:
                    logger.warning(f"Coordinator: QuantGate logic error: {qe}")

                if self.brain.mode != "paper":
                    try:
                        cushion = await self.brain.get_ibkr_cushion()
                        if cushion < 0.15:
                            logger.critical(
                                f"Coordinator [{proposal_id}]  MARGIN SHIELD VETO: Cushion is too low ({cushion:.2%}). Standing down."
                            )
                            return False
                    except Exception as me:
                        logger.warning(
                            f"Coordinator: Margin Shield offline, proceeding with caution: {me}"
                        )

                logger.info(f"Coordinator [{proposal_id}] polling 7-Agent Quorum...")

                # Mandatory gate: Every trade must pass through the Agent A defensive fortress.
                # Runs under Neural Semaphore as it performs 75Y Atlas matching and Neural Lambda calibration.
                async def poll_agent_a():
                    try:
                        # Probes test wiring, not trade quality. Agent A auto-approves.
                        if is_probe:
                            return {
                                "agent": "Agent_A",
                                "vote": "YES",
                                "confidence": 1.0,
                                "reason": "PROBE_AUTO_APPROVE: Wiring test bypass.",
                                "final_lambda": 99.0,
                                "signal_strength": 1.0,
                                "lambda": 1.0,
                                "risk_flag": "False",
                                "regime": self.brain.current_regime,
                                "metadata": {
                                    "pattern": pattern.name,
                                    "entry": pattern.entry,
                                    "stop": pattern.stop,
                                    "target": pattern.target,
                                },
                            }

                        # Guard: ensure ohlcv_1m is a real DataFrame before accessing columns
                        if ohlcv_1m is None or isinstance(ohlcv_1m, str):
                            return {
                                "agent": "Agent_A",
                                "vote": "NO",
                                "reason": "No OHLCV data available.",
                            }

                        # 1. DMS Heartbeat
                        if self.brain.dms:
                            self.brain.dms.record_heartbeat("AGENT_A")

                        # 2. Derive context for Agent A
                        tension = (
                            self.brain.dhatu_oracle.calculate_spread_tension(
                                bid=float(ohlcv_1m["low"].tail(1).item()),
                                ask=float(ohlcv_1m["high"].tail(1).item()),
                                volume=float(ohlcv_1m["volume"].tail(1).item()),
                            )
                            if self.brain.dhatu_oracle
                            else 0.0
                        )

                        # Calculate entropy using the brain's calc
                        p_before = 0.5
                        p_after = pattern.confidence / 100.0
                        entropy_score = self.brain.entropy_calc.signal_entropy(p_before, p_after)

                        closes = ohlcv_1m["close"].to_numpy()
                        resistances = [float(np.percentile(closes, 90)), float(np.max(closes))]
                        timeframes = [("1m", ohlcv_1m)]

                        # Trend 5d/1m
                        trend_5d = "bull"
                        trend_1m = "bull"
                        try:
                            df_h1 = await asyncio.to_thread(
                                pd.read_sql_query,
                                "SELECT close FROM ohlcv WHERE symbol=? AND timeframe='1h' ORDER BY timestamp DESC LIMIT 500",
                                self.brain.db_conn,
                                params=[symbol],
                            )
                            if len(df_h1) >= 5:
                                trend_5d = (
                                    "bull"
                                    if df_h1["close"].iloc[0] > df_h1["close"].iloc[4]
                                    else "bear"
                                )
                            if len(df_h1) >= 20:
                                trend_1m = (
                                    "bull"
                                    if df_h1["close"].iloc[0] > df_h1["close"].iloc[19]
                                    else "bear"
                                )
                        except Exception:
                            trend_5d = (
                                "bull" if ohlcv_1m["close"].tail(1).item() > ohlcv_1m["close"].tail(5).to_numpy()[-1] else "bear"
                            )
                            trend_1m = (
                                "bull" if ohlcv_1m["close"].tail(1).item() > ohlcv_1m["close"].tail(20).to_numpy()[-1] else "bear"
                            )

                        # 3. Dynamic ATR for sizing resonance
                        # Convert to numpy FIRST — np.maximum cannot handle Polars Series
                        # (shift(1) introduces a null which makes numpy fall back to dtype('O'))
                        _h = ohlcv_1m["high"].to_numpy(allow_copy=True).astype(float)
                        _l = ohlcv_1m["low"].to_numpy(allow_copy=True).astype(float)
                        _c = ohlcv_1m["close"].to_numpy(allow_copy=True).astype(float)
                        _hl = _h - _l
                        _hc = np.abs(_h[1:] - _c[:-1])
                        _lc = np.abs(_l[1:] - _c[:-1])
                        _tr = np.maximum(_hl[1:], np.maximum(_hc, _lc))
                        atr_20 = float(np.mean(_tr[-20:])) if len(_tr) >= 20 else float(np.mean(_tr)) if len(_tr) > 0 else 0.5

                        # 4. EXPLICIT AGENT A VALIDATION (The Defensive Fortress)
                        # Wrapped in to_thread because it's heavy math/neural logic.
                        # Agent A now queries Agent D's live win rates for Kelly edge calc.
                        learned = getattr(self.brain, "_learned_win_rates", {})
                        regime_key = f"{pattern.name}:{self.brain.current_regime}"
                        learned_wr = learned.get(regime_key) or learned.get(pattern.name)
                        a_result = await asyncio.to_thread(
                            agent_a_validate_trade,
                            pattern=pattern,
                            budget_monitor=self.brain.budget_monitor,
                            entropy_calc=self.brain.entropy_calc,
                            escape_classifier=self.brain.escape_classifier,
                            mtf_aligner=self.brain.mtf_aligner,
                            atlas=self.brain.sovereign_atlas,
                            oracle=self.brain.dhatu_oracle,
                            neural_engine=self.brain.neural_engine,
                            regime_classifier=self.brain.regime_classifier_neural,
                            live_learner=self.brain.live_learner,
                            ohlcv_df=ohlcv_1m,
                            volume_surge=(
                                ohlcv_1m["volume"].tail(1).item() > ohlcv_1m["volume"][-20:-1].mean() * 2.0
                            ),
                            trend_5d=trend_5d,
                            trend_1m=trend_1m,
                            entropy_score=entropy_score,
                            resistances=resistances,
                            timeframes=timeframes,
                            symbol=symbol,
                            shares=shares,
                            atr_20=atr_20,
                            dd_level=self.brain.ibkr_drawdown.level.value,
                            tension=tension,
                            agent_d_win_rate=learned_wr,
                            agent_d_n_trades=self.brain.live_learner._n_trades
                            if hasattr(self.brain, "live_learner")
                            else 0,
                        )

                        return a_result
                    except Exception as ae:
                        logger.error(f"Coordinator: Agent A Fortress Check FAILED: {ae}")
                        return {
                            "agent": "Agent_A",
                            "vote": "NO",
                            "reason": f"Neural Validation Error: {str(ae)[:50]}",
                        }

                agent_a_out = await _poll_neural_safe("Agent_A", poll_agent_a)

                if agent_a_out["vote"] == "NO":
                    logger.info(
                        f"Coordinator [{proposal_id}]  SOVEREIGN VETO: Agent A rejected proposal. {agent_a_out.get('reason')}"
                    )
                    if self.brain.bus:
                        await self.brain.bus.publish(
                            "consensus.update",
                            {
                                "symbol": symbol,
                                "phase": "VETO",
                                "decision": "REJECT",
                                "reason": agent_a_out.get("reason"),
                                "votes": [agent_a_out],
                                "timestamp": time.time() * 1000,
                            },
                        )
                    return False

                if self.brain.bus:
                    await self.brain.bus.publish(
                        "consensus.update",
                        {
                            "symbol": symbol,
                            "phase": "AGENT_A_OK",
                            "decision": "VOTING",
                            "votes": [agent_a_out],
                            "timestamp": time.time() * 1000,
                        },
                    )

                async def poll_agent_d():
                    """Agent D: Historical Learning & Significance Mind."""
                    try:
                        learned = getattr(self.brain, "_learned_win_rates", {})
                        regime_key = f"{pattern.name}:{self.brain.current_regime}"
                        learned_wr = learned.get(regime_key) or learned.get(pattern.name)

                        # Direct call to standardized consensus (Alpha Brain Integration)
                        agent_d_vote = self.brain.live_learner.evaluate_proposal(
                            pattern.name, self.brain.current_regime
                        )

                        # Only hard-veto if we have statistically significant data
                        # (n >= 30). Below that, trust the built-in evaluate_proposal
                        # which uses data ratings and defaults to neutral.
                        agent_d_n = (
                            self.brain.live_learner._n_trades
                            if hasattr(self.brain, "live_learner")
                            else 0
                        )
                        if (
                            learned_wr is not None
                            and isinstance(learned_wr, float)
                            and learned_wr < 0.40
                            and agent_d_n >= 30
                        ):
                            agent_d_vote["vote"] = "NO"
                            agent_d_vote["reason"] = (
                                f" IMPERIAL VETO: Internal WR too low ({learned_wr:.2%}, n={agent_d_n})"
                            )

                        return agent_d_vote
                    except Exception as e:
                        logger.error(f"Coordinator: Agent D poll failed: {e}")
                        return {
                            "agent": "Agent_D",
                            "vote": "ABSTAIN",
                            "confidence": 0.0,
                            "reason": f"Fallback abstain: {str(e)[:80]}",
                            "timestamp": timestamp,
                        }

                async def poll_oracle():
                    """Dhatu Oracle: (SOLUTION 5) Uses Background State with High-Fidelity Fallback."""
                    state = self.brain.conviction_state.get("Dhatu_Oracle")
                    if state and "timestamp" in state:
                        ts = state["timestamp"]
                        # Handle both string and numeric timestamps
                        if isinstance(ts, (int, float)):
                            _sec = ts / 1e9 if ts > 1e16 else (ts / 1e3 if ts > 1e11 else ts)
                            ts = datetime.fromtimestamp(_sec, tz=timezone.utc)
                        else:
                            ts = dtparser.parse(ts)
                        if (datetime.now(timezone.utc) - ts).total_seconds() < 90:
                            return state

                    try:
                        if self.brain.dhatu_oracle is None:
                            raise RuntimeError("DhatuOracle not configured")
                        logger.info(
                            "Coordinator: Background Oracle stale. Falling back to Live Synthesis..."
                        )
                        return await asyncio.to_thread(
                            self.brain.dhatu_oracle.evaluate_proposal, shared_context
                        )
                    except Exception as e:
                        logger.warning(f"Coordinator: Oracle Live Fallback failed: {e}")
                        return {
                            "agent": "Dhatu_Oracle",
                            "vote": "ABSTAIN",
                            "confidence": 0.0,
                            "reason": "Oracle Offline (abstained)",
                            "timestamp": timestamp,
                        }

                async def poll_swarm():
                    """Swarm Predictor: (SOLUTION 5) Uses Background State with High-Fidelity Fallback."""
                    if self.brain.swarm_predictor is None:
                        return {
                            "agent": "Swarm_Predictor",
                            "vote": "ABSTAIN",
                            "confidence": 0.0,
                            "reason": "SwarmPredictor not configured",
                            "timestamp": timestamp,
                        }

                    state = self.brain.conviction_state.get("Swarm_Predictor")
                    if state and "timestamp" in state:
                        ts = state["timestamp"]
                        # Handle both string and numeric timestamps
                        if isinstance(ts, (int, float)):
                            _sec = ts / 1e9 if ts > 1e16 else (ts / 1e3 if ts > 1e11 else ts)
                            ts = datetime.fromtimestamp(_sec, tz=timezone.utc)
                        else:
                            ts = dtparser.parse(ts)
                        if (datetime.now(timezone.utc) - ts).total_seconds() < 90:
                            return state

                    try:
                        logger.info(
                            "Coordinator: Background Swarm stale. Falling back to Live Collective Intelligence..."
                        )
                        return await self.brain.swarm_predictor.evaluate_proposal(shared_context)
                    except Exception as e:
                        logger.warning(f"Coordinator: Swarm Live Fallback failed: {e}")
                        return {
                            "agent": "Swarm_Predictor",
                            "vote": "ABSTAIN",
                            "confidence": 0.0,
                            "reason": "Swarm Offline (abstained)",
                            "timestamp": timestamp,
                        }

                # -- QUORUM ASSEMBLY (STRICT UNIQUENESS) --
                vote_registry: Dict[str, Dict[str, Any]] = {}

                try:
                    tier1_results = await self.exoskeleton.run_parallel_tier(shared_context)
                    for res in tier1_results:
                        if res and "agent" in res:
                            vote_registry[res["agent"]] = res

                    dummy_tail = self.exoskeleton.evaluate_dictatorship(tier1_results, timestamp)
                    if dummy_tail:
                        for res in dummy_tail:
                            vote_registry[res["agent"]] = res
                except Exception as exo_err:
                    logger.error(
                        f"Coordinator: Apex Exoskeleton failure, reverting to Imperial Core: {exo_err}"
                    )
                    tier1_agents = {
                        "Agent_B": lambda: self.brain.belief_tracker.evaluate_proposal(
                            shared_context
                        ),
                        "Agent_C": lambda: (
                            self.brain.dms.record_heartbeat("AGENT_C") if self.brain.dms else None,
                            self.brain.portfolio_guard.evaluate_proposal(shared_context, "Agent_C"),
                        )[1],
                        "Risk_Guard": lambda: self.brain.correlation_guard.evaluate_proposal(
                            shared_context, "Risk_Guard"
                        ),
                        "Agent_D": poll_agent_d,
                        "Agent_E": lambda: self.brain.correlation_guard.evaluate_proposal(
                            shared_context, "Agent_E"
                        ),
                        "Agent_F": lambda: self.brain.vix_protocol.evaluate_proposal(
                            shared_context, "Agent_F"
                        ),
                        "Agent_G": lambda: self.brain.mind_architect.evaluate_proposal(
                            shared_context
                        ),
                    }

                    tier1_results = []
                    for name, func in tier1_agents.items():
                        res = await _poll_safe(name, func)
                        vote_registry[name] = res
                        tier1_results.append(res)
                    dummy_tail = None

                # Agent A is mandatory and always unique
                vote_registry["Agent_A"] = agent_a_out

                if not dummy_tail:
                    no_agents_tier1 = [
                        str(v.get("agent", "UNKNOWN"))
                        for v in vote_registry.values()
                        if v.get("vote") == "NO"
                        and v.get("agent")
                        in ["Agent_B", "Agent_C", "Risk_Guard", "Agent_E", "Agent_F", "Agent_G"]
                    ]
                    if no_agents_tier1 and not is_probe:
                        veto_list = ", ".join(no_agents_tier1)
                        logger.warning(
                            f"Coordinator [{proposal_id}]  EARLY EXIT: {veto_list} voted NO. Standing down."
                        )
                        dummy_tail = [
                            {
                                "agent": "Dhatu_Oracle",
                                "vote": "NO",
                                "confidence": 0.0,
                                "reason": f"Skipped (blocked by {veto_list})",
                                "timestamp": timestamp,
                            },
                            {
                                "agent": "Swarm_Predictor",
                                "vote": "NO",
                                "confidence": 0.0,
                                "reason": f"Skipped (blocked by {veto_list})",
                                "timestamp": timestamp,
                            },
                            {
                                "agent": "Mind_Ultrathink",
                                "vote": "NO",
                                "confidence": 0.0,
                                "reason": f"Skipped (blocked by {veto_list})",
                                "timestamp": timestamp,
                            },
                        ]
                        for res in dummy_tail:
                            vote_registry[res["agent"]] = res

                if self.brain.bus:
                    await self.brain.bus.publish(
                        "consensus.update",
                        {
                            "symbol": symbol,
                            "phase": "STAGE_1_OK",
                            "decision": "VOTING",
                            "votes": list(vote_registry.values()),
                            "timestamp": time.time() * 1000,
                        },
                    )

                if not dummy_tail:
                    logger.info(
                        f"Coordinator [{proposal_id}]: Stage 1 Clear. Entering Neural Gate for Gated agents..."
                    )
                    try:
                        gated_agents = [
                            ("Dhatu_Oracle", poll_oracle),
                            ("Swarm_Predictor", poll_swarm),
                            (
                                "Mind_Ultrathink",
                                lambda: self.brain.mind_ultrathink.evaluate_proposal(
                                    shared_context
                                ),
                            ),
                        ]
                        live_only_agents = []

                        if self.brain.native_slm and self.brain.native_slm.is_available:
                            live_only_agents.append(
                                (
                                    "Native_SLM",
                                    lambda: self.brain.native_slm.evaluate_proposal(shared_context),
                                )
                            )

                        _vram_pct = 0  # LLM purged — no VRAM contention

                        gated_votes = []
                        background_success = True
                        for name, _ in gated_agents:
                            cache_key = (
                                f"{name}:{symbol}"
                                if name in ["Swarm_Predictor", "Mind_Ultrathink"]
                                else name
                            )
                            state = self.brain.conviction_state.get(cache_key)
                            state_ts = state.get("timestamp") if state else None
                            should_call = not state or not state_ts
                            if state_ts and not should_call:
                                # Handle both string and numeric timestamps
                                if isinstance(state_ts, (int, float)):
                                    _sec = (
                                        state_ts / 1e9
                                        if state_ts > 1e16
                                        else (state_ts / 1e3 if state_ts > 1e11 else state_ts)
                                    )
                                    ts = datetime.fromtimestamp(_sec, tz=timezone.utc)
                                else:
                                    ts = dtparser.parse(state_ts)
                                should_call = (datetime.now(timezone.utc) - ts).total_seconds() > 90
                            if should_call:
                                background_success = False
                                break
                            state["timestamp"] = timestamp
                            gated_votes.append(state)

                        if not background_success:
                            logger.info(
                                "Coordinator: Background Conviction Stale/Missing. Reverting to Parallel Neural Gate..."
                            )

                            # Uses _poll_neural_safe to manage VRAM contention serialy but gathered in parallel.
                            names = [n for n, _ in gated_agents]
                            funcs = [f for _, f in gated_agents]

                            results = await asyncio.gather(
                                *[
                                    asyncio.wait_for(_poll_neural_safe(name, func), timeout=120.0)
                                    for name, func in zip(names, funcs, strict=False)
                                ],
                                return_exceptions=True,
                            )

                            for name, res in zip(names, results, strict=False):
                                if isinstance(res, (Exception, asyncio.TimeoutError)):
                                    logger.error(f"Neural Gate: {name} Failed or Timed Out: {res}")
                                    gated_votes.append(
                                        {
                                            "agent": name,
                                            "vote": "ABSTAIN",
                                            "confidence": 0.0,
                                            "reason": "Latency/Error abstain",
                                            "timestamp": timestamp,
                                        }
                                    )
                                else:
                                    gated_votes.append(res)

                        if live_only_agents:
                            names = [n for n, _ in live_only_agents]
                            funcs = [f for _, f in live_only_agents]
                            results = await asyncio.gather(
                                *[
                                    asyncio.wait_for(_poll_neural_safe(name, func), timeout=120.0)
                                    for name, func in zip(names, funcs, strict=False)
                                ],
                                return_exceptions=True,
                            )
                            for name, res in zip(names, results, strict=False):
                                if isinstance(res, (Exception, asyncio.TimeoutError)):
                                    logger.error(f"Neural Gate: {name} Failed or Timed Out: {res}")
                                    gated_votes.append(
                                        {
                                            "agent": name,
                                            "vote": "ABSTAIN",
                                            "confidence": 0.0,
                                            "reason": "Latency/Error abstain",
                                            "timestamp": timestamp,
                                        }
                                    )
                                else:
                                    gated_votes.append(res)

                        for res in gated_votes:
                            if res and "agent" in res:
                                vote_registry[res["agent"]] = res
                                # Update Conviction State for caching
                                if res.get("confidence", 0) > 0:
                                    cache_key = (
                                        f"{res['agent']}:{symbol}"
                                        if res["agent"] in ["Swarm_Predictor", "Mind_Ultrathink"]
                                        else res["agent"]
                                    )
                                    self.brain.conviction_state[cache_key] = res
                    except Exception as gated_e:
                        logger.error(f"Coordinator: Gated Intelligence failure: {gated_e}")
                        for name, _ in gated_agents:
                            err_vote = {
                                "agent": name,
                                "vote": "ABSTAIN",
                                "confidence": 0.0,
                                "reason": "Neural Error abstain",
                                "timestamp": timestamp,
                            }
                            vote_registry[name] = err_vote

                if self.brain.bus:
                    await self.brain.bus.publish(
                        "consensus.update",
                        {
                            "symbol": symbol,
                            "phase": "STAGE_2_OK",
                            "decision": "VOTING",
                            "votes": list(vote_registry.values()),
                            "timestamp": time.time() * 1000,
                        },
                    )

                # Final List Conversion (Guarantees no duplicates)
                all_votes = list(vote_registry.values())

                # AUDIT AGENT: Check for cognitive bias in the quorum
                try:
                    if self.brain.audit_agent and all_votes:
                        audit_report = self.brain.audit_agent.full_audit(all_votes)
                        if audit_report.get("issues"):
                            logger.warning(
                                "Coordinator [%s]: AuditAgent detected issues: %s",
                                symbol,
                                audit_report["issues"],
                            )
                except Exception as audit_err:
                    logger.debug("Coordinator [%s]: AuditAgent error: %s", symbol, audit_err)

                # COGNITIVE DIVERSITY: measure HHI of vote distribution
                try:
                    if self._diversity_enforcer and all_votes:
                        _vote_counts: Dict[str, int] = {}
                        for _v in all_votes:
                            _vt = _v.get("vote", "ABSTAIN")
                            _vote_counts[_vt] = _vote_counts.get(_vt, 0) + 1
                        _div_report = self._diversity_enforcer.diversity_report(_vote_counts)
                        if not _div_report["is_diverse"]:
                            logger.warning(
                                "Coordinator [%s]: Low vote diversity HHI=%.2f — herding risk",
                                symbol, _div_report["hhi"],
                            )
                except Exception as _div_err:
                    logger.debug("Coordinator [%s]: DiversityEnforcer error: %s", symbol, _div_err)

                # ENSEMBLE DISTILLER: record model outputs for accuracy tracking
                try:
                    if self._ensemble_distiller and all_votes:
                        _distilled = self._ensemble_distiller.distill(
                            [{"model": v.get("agent", "?"), "vote": v.get("vote", "ABSTAIN"),
                              "confidence": v.get("confidence", 0.5)} for v in all_votes]
                        )
                        logger.debug(
                            "Coordinator [%s]: Ensemble distilled vote=%s conf=%.1f%%",
                            symbol, _distilled["vote"], _distilled["confidence"] * 100,
                        )
                except Exception as _ens_err:
                    logger.debug("Coordinator [%s]: EnsembleDistiller error: %s", symbol, _ens_err)

                decision = await self.brain.decision_engine.evaluate(shared_context, all_votes)
                # Implementation: decision_engine can return None on internal error; guard before .get() calls
                if not decision or "decision" not in decision:
                    logger.error("Coordinator [%s]: decision engine returned invalid output: %s", symbol, decision)
                    return False

                if not is_probe:
                    self.exoskeleton.store_cortex_cache(
                        symbol, pattern.entry, decision, all_votes, shares
                    )

                if task is None and not is_probe:
                    task = self.brain.task_manager.spawn_trade(symbol, pattern.to_dict())

                return await self._execute_decision(
                    symbol, decision, pattern, all_votes, is_probe, shares, task
                )

        except Exception as e:
            logger.error(
                f"Coordinator Error inside Sovereign Lifecycle for {symbol}: {e}", exc_info=True
            )
            return False
        finally:
            if not is_probe:
                self._finalize_open_task(
                    task,
                    "LIFECYCLE_EXIT",
                    "coordinator returned without terminal task state",
                )
            self._pending_vets.discard(symbol)
            if hasattr(self.brain, "_vetting_cooldowns"):
                self.brain._vetting_cooldowns[symbol] = datetime.now(timezone.utc)

    async def _execute_decision(
        self, symbol, decision, pattern, all_votes, is_probe, shares=0, task=None
    ) -> bool:
        """The dedicated execution nexus for the Sovereign system."""
        try:
            proposal_id = all_votes[0].get("proposal_id", "CACHE") if all_votes else "CACHE"
            decision = self._maybe_promote_paper_exploration(
                symbol=symbol,
                decision=decision,
                pattern=pattern,
                all_votes=all_votes,
                shares=shares,
                is_probe=is_probe,
            )
            if decision.get("paper_exploration"):
                exploration_cap = max(
                    1, int(os.environ.get("SOVEREIGN_PAPER_EXPLORATION_MAX_SHARES", "1"))
                )
                shares = min(int(shares), exploration_cap)

            if decision["decision"] == "EXECUTE" or is_probe:
                if is_probe:
                    if task:
                        task.log(
                            "EXECUTION_PHANTOM: System verified operational. Standing down (Probe Mode)."
                        )
                    logger.info(
                        f"Coordinator [{proposal_id}]  PHANTOM PROBE SUCCESS: System wiring is 100% OPERATIONAL."
                    )
                    return True

                data_block_reason = self._entry_data_block_reason(symbol)
                if data_block_reason:
                    if task:
                        task.set_phase("ENTRY_DATA_VETO", data_block_reason)
                        task.finalize("VETOED")
                    logger.warning(
                        "Coordinator [%s] ENTRY_DATA_VETO: %s blocked - %s.",
                        proposal_id,
                        symbol,
                        data_block_reason,
                    )
                    LEDGER.record_veto(symbol=symbol, reason=f"ENTRY_DATA_VETO: {data_block_reason}")
                    return False

                # BACKTEST VALIDATION GATE (Phase 1 Edge Check)
                backtest_enabled = str(os.environ.get("SOVEREIGN_BACKTEST_GATE", "1")).strip() in ("1", "true", "yes")
                if backtest_enabled and pattern:
                    try:
                        validator = getattr(self, "_backtest_validator", None)
                        if validator is None:
                            db_path = getattr(self.brain, "db_path", "data/trading.db")
                            self._backtest_validator = BacktestValidator(db_path=str(db_path))
                            validator = self._backtest_validator
                        bt_result = await validator.validate_pattern(symbol, pattern)
                        if not bt_result.passed:
                            blockers = ", ".join(bt_result.blockers)
                            if task:
                                task.set_phase("BACKTEST_VETO", blockers)
                                task.finalize("VETOED")
                            logger.warning(
                                "Coordinator [%s] BACKTEST_VETO: %s blocked - %s.",
                                proposal_id,
                                symbol,
                                blockers,
                            )
                            LEDGER.record_veto(
                                symbol=symbol,
                                reason=f"BACKTEST_VETO: {blockers}",
                            )
                            return False
                        logger.info(
                            "Coordinator [%s] BACKTEST_OK: %s passed historical validation (PF=%.2f WR=%.1f).",
                            proposal_id,
                            symbol,
                            bt_result.profit_factor,
                            bt_result.win_rate * 100,
                        )
                    except Exception as bt_exc:
                        reason = f"validation_error: {type(bt_exc).__name__}: {bt_exc}"
                        if task:
                            task.set_phase("BACKTEST_VETO", reason)
                            task.finalize("VETOED")
                        logger.exception(
                            "Coordinator [%s] BACKTEST_VETO: %s validation failed closed",
                            proposal_id,
                            symbol,
                        )
                        LEDGER.record_veto(symbol=symbol, reason=f"BACKTEST_VETO: {reason}")
                        return False

                # PSYCHOLOGY SAFETY GATE (Stress Veto)
                try:
                    from stress_veto import get_stress_veto
                    stress_veto = get_stress_veto()
                    analysis = stress_veto.analyze_stress()
                    if analysis.stress_detected and analysis.recommendation == "LOCKOUT":
                        if task:
                            task.set_phase("STRESS_VETO", analysis.stress_type)
                            task.finalize("VETOED")
                        logger.warning(
                            "Coordinator [%s] STRESS_VETO: %s blocked — %s (severity: %.2f). Cooldown: %d min.",
                            proposal_id,
                            symbol,
                            analysis.reason,
                            analysis.severity,
                            analysis.cooldown_minutes,
                        )
                        LEDGER.record_veto(
                            symbol=symbol,
                            reason=f"STRESS_VETO: {analysis.stress_type} — {analysis.reason}",
                        )
                        return False
                    if analysis.stress_detected:
                        logger.info(
                            "Coordinator [%s] STRESS_WARNING: %s — %s (severity: %.2f)",
                            proposal_id,
                            symbol,
                            analysis.reason,
                            analysis.severity,
                        )
                except Exception as sv_exc:
                    logger.debug("Coordinator [%s] stress veto error for %s: %s", proposal_id, symbol, sv_exc)

                if task:
                    task.log(
                        f"EXECUTION_START: Routing {shares} shares to {self.brain.active_broker}."
                    )
                logger.info(f"Coordinator [{proposal_id}] [QUORUM_OK] Executing trade for {symbol}")

                try:
                    ledger_votes = {
                        v.get(
                            "agent", "Unknown"
                        ): f"{v.get('vote')} ({int(v.get('confidence', 0) * 100)}%) - {v.get('reason', '')}"
                        for v in all_votes
                    }
                    LEDGER.record_entry(
                        symbol=symbol,
                        pattern=getattr(pattern, "name", "Pattern"),
                        confidence=decision.get("confidence", 0.0) * 100,
                        agent_votes=ledger_votes,
                        triggered_by=proposal_id,
                        event_type="EXECUTION",
                        meta={"shares": shares, "regime": self.brain.current_regime},
                    )
                except Exception as le:
                    logger.debug(f"DecisionLedger execution audit skipped: {le}")

                is_long = pattern.entry > pattern.stop
                order_side = "BUY" if is_long else "SELL"
                urgency = "HIGH" if self.brain.current_regime in ["VOLATILE", "TRENDING"] else "LOW"

                if self.brain.active_broker == "MAINTENANCE":
                    if task:
                        task.log("MAINTENANCE_VETO: Market rollover detected. Aborting.")
                    logger.warning(
                        f"Coordinator [{proposal_id}]  MAINTENANCE STAND-DOWN: Market rollover in progress. Order skipped."
                    )
                    return False

                if getattr(self.brain, "db_conn", None):
                    try:
                        broker_key = self.brain.active_broker.lower()
                        row = self.brain.db_conn.execute(
                            "SELECT id FROM trades WHERE instrument=? AND broker=? "
                            "AND outcome='OPEN' ORDER BY id DESC LIMIT 1",
                            (symbol, broker_key),
                        ).fetchone()
                        if row:
                            open_id = row[0]
                            if task:
                                task.set_phase(
                                    "OPEN_DUPLICATE_BLOCK",
                                    f"existing trade id {open_id}",
                                )
                                task.finalize("VETOED")
                            logger.warning(
                                "Coordinator [%s] duplicate OPEN guard blocked %s on %s "
                                "(trade id=%s)",
                                proposal_id,
                                symbol,
                                broker_key,
                                open_id,
                            )
                            return False
                    except Exception as guard_err:
                        logger.debug("Duplicate OPEN guard skipped for %s: %s", symbol, guard_err)

                # Execution with SE-11 Brackets & Ghost Expansion
                order_id = None
                if self.brain.active_broker == "IBKR":
                    if task:
                        task.set_phase("ORDER_SUBMIT", "IBKR")
                    order_id = await self.brain._place_ibkr_order(
                        symbol=symbol,
                        direction=order_side,
                        shares=shares,
                        urgency=urgency,
                        limit_price=pattern.entry,
                        stop_price=pattern.stop,
                        target_price=pattern.target,
                        **decision,
                    )
                elif self.brain.active_broker == "MT5":
                    if task:
                        task.set_phase("ORDER_SUBMIT", "MT5")
                    order_id = await self.brain._place_mt5_order(
                        symbol=symbol,
                        direction=order_side,
                        shares=shares,
                        limit_price=pattern.entry,
                        stop_price=pattern.stop,
                        target_price=pattern.target,
                        **decision,
                    )
                if order_id:
                    if task:
                        task.set_phase("ORDER_ACCEPTED", str(order_id))
                        task.log(f"EXECUTION_CONFIRMED: Order {order_id} active.")
                        task.finalize("SUCCESS")

                    quorum_count = len(all_votes)
                    # Compute Intent String
                    intent = "UNKNOWN"
                    if pattern.category == "HOLD":
                        intent = "Hold"
                    elif pattern.category == "SWING":
                        intent = "Swing"
                    elif pattern.category == "SCALP":
                        intent = "Scalp"
                    elif pattern.category == "HFT":
                        intent = "HFT"

                    side_str = "LONG" if order_side == "BUY" else "SHORT"
                    full_intent = f"{side_str} {intent}"

                    await send_telegram_alert(
                        self._format_execution_alert(
                            symbol=symbol,
                            order_id=order_id,
                            pattern=pattern,
                            order_side=order_side,
                            intent=intent,
                            shares=shares,
                            quorum_count=quorum_count,
                            decision=decision,
                            task_id=task.id if task else "N/A",
                        )
                    )

                    from system_types import Position

                    broker_name = self.brain.active_broker.lower()
                    broker_confirmed_costs = (
                        broker_name == "ibkr" and getattr(self.brain, "mode", "paper") != "paper"
                    )
                    estimated_entry_commission = max(2.0, shares * 0.005)
                    estimated_entry_slippage = shares * pattern.entry * 0.0005
                    signed_shares = shares if is_long else -shares
                    pos = Position(
                        symbol=symbol,
                        qty=signed_shares,
                        entry_price=pattern.entry,
                        entry_time=datetime.now(timezone.utc),
                        pattern=pattern.name,
                        initial_belief=0.5,
                        current_belief=0.5,
                        initial_stop=pattern.stop,
                        stop_loss=pattern.stop,
                        take_profit=pattern.target,
                        trade_id=str(order_id),
                        task_id=task.id if task else "N/A",
                        account_type=broker_name,
                        catalyst_score=(all_votes[0].get("confidence", 0.5) if all_votes else 0.5)
                        * 100,
                        regime_at_entry=self.brain.current_regime,
                        commission_cost=0.0
                        if broker_confirmed_costs
                        else estimated_entry_commission,
                        slippage_cost=0.0
                        if broker_confirmed_costs
                        else estimated_entry_slippage,
                    )
                    pos.meta.update(
                        {
                            "intent": full_intent,
                            "execution_mode": getattr(self.brain, "mode", "UNKNOWN"),
                            "execution_broker": self.brain.active_broker,
                            "order_id": str(order_id),
                            "paper_exploration": bool(decision.get("paper_exploration")),
                            "decision_reason": str(decision.get("reason", ""))[:500],
                            "entry_qty_signed": signed_shares,
                            "intended_entry_price": pattern.entry,
                            "estimated_entry_commission": estimated_entry_commission,
                            "estimated_entry_slippage": estimated_entry_slippage,
                        }
                    )
                    async with self.brain._state_lock:
                        self.brain.positions.append(pos)
                    await self.brain._log_trade_entry(pos)

                    # AUTO THESIS GENERATION: document the trade rationale
                    try:
                        from reports.thesis_gen import AutoThesisGenerator
                        thesis_gen = AutoThesisGenerator()
                        vix_val = await self.brain._get_vix()
                        macro_ctx = {
                            "vix": f"{vix_val:.1f}" if vix_val else "Unknown",
                            "rates": "Stable",
                            "sector_momentum": getattr(self.brain, "current_regime", "Neutral"),
                            "bias": getattr(self.brain, "current_regime", "Neutral"),
                        }
                        vote_map = {
                            v.get("agent", "unknown"): f"{v.get('vote')} ({int(v.get('confidence', 0) * 100)}%)"
                            for v in all_votes
                        }
                        agent_consensus = {
                            "conviction_score": decision.get("confidence", 0.0),
                            "votes": vote_map,
                        }
                        risk_metrics = {
                            "entry_price": pattern.entry,
                            "stop_loss": pattern.stop,
                            "take_profit": pattern.target,
                            "rr_ratio": getattr(pattern, "r_r_ratio", 0.0),
                            "kelly_pct": 0.0,
                        }
                        thesis_path = thesis_gen.generate_thesis(
                            trade_id=str(proposal_id),
                            ticker=symbol,
                            action="BUY" if is_long else "SELL",
                            size=shares,
                            macro_context=macro_ctx,
                            agent_consensus=agent_consensus,
                            risk_metrics=risk_metrics,
                            order_book_state={},
                        )
                        logger.info(f"Coordinator [{proposal_id}]: Trade thesis generated at {thesis_path}")
                    except Exception as thesis_err:
                        logger.debug(f"Coordinator [{proposal_id}]: Thesis generation failed: {thesis_err}")

                    return True
                else:
                    if task:
                        task.set_phase("ORDER_REJECTED", "broker returned no order id")
                        task.log("EXECUTION_FAILURE: Order rejected by broker.")
                        task.finalize("FAILED")
                    if shares < 1:
                        logger.warning(
                            f"Coordinator [{proposal_id}]  SOVEREIGN STANDDOWN: Order for {symbol} blocked (Zero Size)."
                        )
                        await send_telegram_alert(
                            f" *STANDDOWN: {symbol}*\n"
                            f"Reason: ZERO SIZE (Risk Control)\n"
                            f"ID: {proposal_id}"
                        )
                    else:
                        logger.error(
                            f"Coordinator [{proposal_id}]  EXECUTION FAILURE: Order for {symbol} rejected by broker."
                        )
                        await send_telegram_alert(
                            f" *EXECUTION FAILURE: {symbol}*\n"
                            f"Reason: Broker Rejected (Check TWS/Gateway logs)\n"
                            f"ID: {proposal_id}"
                        )
                    return False
            else:
                reason = decision.get("reason", "Consensus No")
                logger.info(
                    f"Coordinator [{proposal_id}]  VETO: {symbol} rejected by decision engine. Reason: {reason}"
                )
                await self._record_rejection(symbol, pattern, decision, all_votes, shares)

                await send_telegram_alert(f" *VETO: {symbol}*\nReason: {reason}\nID: {proposal_id}")

                # Log the rejected proposal as a 'Shadow Trade' for post-mortem calibration.
                try:
                    from system_types import Position

                    shadow_key = (symbol, reason)
                    shadow_log = getattr(self.brain, "_shadow_reject_log", {})
                    now_mono = time.monotonic()
                    last_log = float(shadow_log.get(shadow_key, 0.0))
                    log_shadow_reject = now_mono - last_log >= 300.0
                    if not log_shadow_reject:
                        if task:
                            task.log("SHADOW_REJECT_SUPPRESSED: duplicate reject within 5m.")
                    else:
                        shadow_log[shadow_key] = now_mono
                        self.brain._shadow_reject_log = shadow_log

                        shadow_pos = Position(
                            symbol=symbol,
                            qty=shares if shares > 0 else 0,
                            entry_price=pattern.entry,
                            entry_time=datetime.now(timezone.utc),
                            pattern=pattern.name,
                            initial_belief=float(decision.get("confidence", 0.0) or 0.0),
                            current_belief=float(decision.get("confidence", 0.0) or 0.0),
                            initial_stop=pattern.stop,
                            stop_loss=pattern.stop,
                            take_profit=pattern.target,
                            trade_id=f"SHADOW_{proposal_id}",
                            task_id=task.id if task else "N/A",
                            catalyst_score=float(decision.get("confidence", 0.0) or 0.0) * 100.0,
                            dhatu_state=getattr(self.brain, "_oracle_dhatu", "UNKNOWN"),
                            regime_at_entry=getattr(self.brain, "current_regime", "UNKNOWN"),
                            status="SHADOW_REJECTED",
                            meta={"reason": reason, "votes": all_votes},
                        )
                        # We only log to DB, don't add to brain.positions (not a real trade)
                        await self.brain._log_trade_entry(shadow_pos)
                except Exception as shadow_e:
                    logger.debug(f"Shadow Trade Logging failed: {shadow_e}")

                if task:
                    task.set_phase("QUORUM_REJECT", reason)
                    task.log(f"QUORUM_REJECT: {reason}")
                    task.finalize("VETOED")
                logger.info(f"Coordinator [{proposal_id}] [QUORUM_REJECT] {reason}")
                return False

        except Exception as e:
            logger.error(f"Coordinator Error inside Sovereign Lifecycle: {e}", exc_info=True)
            return False
        finally:
            # Use discard() to avoid KeyError if already removed
            self._pending_vets.discard(symbol)
            # Add to a local 'cooldown' in the brain to prevent the scanner from re-submitting for 30s
            if hasattr(self.brain, "_vetting_cooldowns"):
                self.brain._vetting_cooldowns[symbol] = datetime.now(timezone.utc)

    def _vote_metrics(self, all_votes: list[dict[str, Any]]) -> dict[str, Any]:
        yes_votes = 0.0
        no_agents: list[str] = []
        hard_no_agents: list[str] = []
        confidence_sum = 0.0
        active = 0
        for vote in all_votes:
            agent = str(vote.get("agent", "UNKNOWN"))
            choice = vote.get("vote")
            confidence = float(vote.get("confidence", 0.0) or 0.0)
            if choice != "ABSTAIN":
                active += 1
                confidence_sum += confidence
            if choice == "YES":
                yes_votes += 2.0 if agent == "Agent_D" else 1.0
            elif choice == "NO":
                no_agents.append(agent)
                if agent in {"Risk_Guard", "Agent_D", "Dhatu_Oracle"}:
                    hard_no_agents.append(agent)
        avg_confidence = confidence_sum / active if active else 0.0
        return {
            "yes_votes": yes_votes,
            "no_agents": no_agents,
            "hard_no_agents": hard_no_agents,
            "active_voters": active,
            "avg_confidence": avg_confidence,
        }

    def _maybe_promote_paper_exploration(
        self,
        symbol: str,
        decision: dict[str, Any],
        pattern: Any,
        all_votes: list[dict[str, Any]],
        shares: int,
        is_probe: bool,
    ) -> dict[str, Any]:
        """Allow tiny paper-only learning trades on high-quality near misses."""
        if is_probe or decision.get("decision") == "EXECUTE":
            return decision
        if getattr(self.brain, "mode", "") != "ibkr_paper":
            return decision
        if os.environ.get("SOVEREIGN_PAPER_EXPLORATION", "1") != "1":
            return decision
        if shares <= 0:
            return decision

        metrics = self._vote_metrics(all_votes)
        reason = str(decision.get("reason", ""))
        cognitive_only = (
            "Mind_Ultrathink" in metrics["no_agents"]
            and not metrics["hard_no_agents"]
            and all(
                agent in {"Mind_Ultrathink", "Swarm_Predictor"} for agent in metrics["no_agents"]
            )
        )
        enough_fast_agreement = metrics["yes_votes"] >= 5 and metrics["avg_confidence"] >= 0.50
        pattern_conf = float(getattr(pattern, "confidence", 0.0) or 0.0)
        if not (cognitive_only and enough_fast_agreement and pattern_conf >= 65.0):
            return decision

        # STRONG-VETO GUARD: If Mind_Ultrathink's score is below 0.40 the signal is a hard
        # rejection (stat-prob < 40%).  Do NOT override that — it is the primary cause of
        # exploration trades with negative expectancy.
        ut_vote = next(
            (v for v in all_votes if v.get("agent") == "Mind_Ultrathink"), {}
        )
        ut_score = float(ut_vote.get("confidence", 1.0) or 1.0)
        if ut_score < 0.40:
            logger.warning(
                "Coordinator: %s exploration BLOCKED — Mind_Ultrathink hard veto "
                "(score=%.2f < 0.40 threshold).",
                symbol,
                ut_score,
            )
            return decision

        promoted = dict(decision)
        promoted["decision"] = "EXECUTE"
        promoted["confidence"] = min(0.61, max(float(decision.get("confidence", 0.0) or 0.0), 0.50))
        promoted["reason"] = (
            "IBKR_PAPER_EXPLORATION: tiny paper-only learning order promoted from "
            f"near-miss veto. Original reason: {reason[:180]}"
        )
        promoted["paper_exploration"] = True
        logger.warning(
            "Coordinator: %s promoted to IBKR paper exploration "
            "(yes=%.1f active=%s conf=%.2f pattern_conf=%.1f).",
            symbol,
            metrics["yes_votes"],
            metrics["active_voters"],
            metrics["avg_confidence"],
            pattern_conf,
        )
        return promoted

    async def _record_rejection(
        self,
        symbol: str,
        pattern: Any,
        decision: dict[str, Any],
        all_votes: list[dict[str, Any]],
        shares: int,
    ) -> None:
        """Persist rejection causes separately from real trade rows."""

        def _sync_record() -> None:
            conn = getattr(self.brain, "db_conn", None)
            if conn is None:
                return
            try:
                metrics = self._vote_metrics(all_votes)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS decision_rejections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        pattern TEXT,
                        regime TEXT,
                        dhatu_state TEXT,
                        decision_reason TEXT,
                        confidence REAL,
                        shares INTEGER,
                        yes_votes REAL,
                        active_voters INTEGER,
                        no_agents TEXT,
                        votes_json TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO decision_rejections (
                        timestamp, symbol, pattern, regime, dhatu_state,
                        decision_reason, confidence, shares, yes_votes, active_voters,
                        no_agents, votes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        symbol,
                        getattr(pattern, "name", "UNKNOWN"),
                        getattr(self.brain, "current_regime", "UNKNOWN"),
                        getattr(self.brain, "_oracle_dhatu", "UNKNOWN"),
                        str(decision.get("reason", ""))[:1000],
                        float(decision.get("confidence", 0.0) or 0.0),
                        int(shares or 0),
                        float(metrics["yes_votes"]),
                        int(metrics["active_voters"]),
                        ",".join(metrics["no_agents"]),
                        json.dumps(all_votes, default=str)[:12000],
                    ),
                )
                conn.commit()
            except Exception as exc:
                logger.debug("Decision rejection telemetry skipped for %s: %s", symbol, exc)

        await asyncio.to_thread(_sync_record)
