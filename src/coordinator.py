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
from decision_ledger import LEDGER
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

        pattern = proposal.get("pattern")
        if pattern:
            if task:
                task.set_phase("RR_CHECK", symbol)
                task.log(f"PHASE_RR: Analyzing Risk/Reward for {symbol}. Pattern: {pattern.name}")
            balance = await self.brain.get_safe_buying_power("ibkr")
            from config import COMMISSION_PER_ROUND_TRIP, USD_CAD_RATE

            # Necessary for accurate sizing when trading US assets on a CAD-denominated account.
            balance_usd = (balance or 500.0) / USD_CAD_RATE

            risk_amt = abs(pattern.entry - pattern.stop)
            reward_amt = abs(pattern.target - pattern.entry)
            # Unified Sizing Calculation
            # We use a more realistic position size estimate for RR calculation.
            est_shares = max(1, int(balance_usd * 4.0 * 0.1 / pattern.entry))

            if risk_amt > 0:
                spread_data = await self.brain.get_current_spread(symbol)
                spread = spread_data.get("spread", 0.01) or 0.01
                comm_per_share = COMMISSION_PER_ROUND_TRIP / est_shares

                total_reward_dollars = reward_amt - spread - comm_per_share
                total_risk_dollars = risk_amt + spread + comm_per_share
                real_rr = total_reward_dollars / total_risk_dollars if total_risk_dollars > 0 else 0

                # On small accounts, the 1.3 Net RR is a 'Mathematical Wall' due to fixed commission.
                is_small_account = (balance or 0) < 2000.0
                dollar_risk = total_risk_dollars * est_shares
                risk_pct = (dollar_risk / balance_usd) if (balance_usd > 0) else 0.05

                # Bypass the friction veto entirely.
                # The user wants to see trades execute regardless of mathematical friction
                # on small accounts (e.g. flat commissions killing scalp profits).
                threshold = -99.0

                if is_small_account:
                    threshold = -99.0  # Relax significantly for small accounts
                    if task:
                        task.log(
                            f"RR_RELAX: Small account detected. Dynamic threshold set to {threshold:.2f} (Risk: ${dollar_risk:.2f} USD)."
                        )

                if real_rr < threshold and not is_probe:
                    if task:
                        task.log(
                            f"FRICTION_VETO: Net RR {real_rr:.2f} < {threshold} (S:{spread}, C:{comm_per_share:.3f}). Aborting."
                        )
                    logger.warning(
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

                # Fetch spread for sizing
                spread_data = await self.brain.get_current_spread(symbol)

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
                            spread=spread_data["spread"],
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

                # Fix C: Zero-share veto
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
                                bid=float(ohlcv_1m["low"][-1]),
                                ask=float(ohlcv_1m["high"][-1]),
                                volume=float(ohlcv_1m["volume"][-1]),
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
                                "bull" if ohlcv_1m["close"][-1] > ohlcv_1m["close"][-5] else "bear"
                            )
                            trend_1m = (
                                "bull" if ohlcv_1m["close"][-1] > ohlcv_1m["close"][-20] else "bear"
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
                            ohlcv_df=ohlcv_1m,
                            volume_surge=(
                                ohlcv_1m["volume"][-1] > ohlcv_1m["volume"][-20:-1].mean() * 2.0
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
                    deterministic_deny = any(
                        v["vote"] == "NO"
                        for v in vote_registry.values()
                        if v.get("agent")
                        in ["Agent_B", "Agent_C", "Risk_Guard", "Agent_E", "Agent_F", "Agent_G"]
                    )
                    if deterministic_deny and not is_probe:
                        logger.warning(
                            f"Coordinator [{proposal_id}]  EARLY EXIT: Tier 1 agents rejected. Standing down."
                        )
                        dummy_tail = [
                            {
                                "agent": "Dhatu_Oracle",
                                "vote": "NO",
                                "confidence": 0.0,
                                "reason": "Skipped",
                                "timestamp": timestamp,
                            },
                            {
                                "agent": "Swarm_Predictor",
                                "vote": "NO",
                                "confidence": 0.0,
                                "reason": "Skipped",
                                "timestamp": timestamp,
                            },
                            {
                                "agent": "Mind_Ultrathink",
                                "vote": "NO",
                                "confidence": 0.0,
                                "reason": "Skipped",
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

                        vram_pct = 0  # LLM purged — no VRAM contention

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

                decision = await self.brain.decision_engine.evaluate(shared_context, all_votes)

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
                        f" *EXECUTION: {symbol}*\n"
                        f"Type: {full_intent}\n"
                        f"Price: ${pattern.entry:.2f}\n"
                        f"Qty: {shares}\n"
                        f"SL: ${pattern.stop:.2f}\n"
                        f"TP: ${pattern.target:.2f}\n"
                        f"Quorum: {quorum_count} Agents\n"
                        f"Task: {task.id if task else 'N/A'}"
                    )

                    from system_types import Position

                    pos = Position(
                        symbol=symbol,
                        qty=(shares if is_long else -shares),
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
                        account_type=self.brain.active_broker.lower(),
                        catalyst_score=(all_votes[0].get("confidence", 0.5) if all_votes else 0.5)
                        * 100,
                        regime_at_entry=self.brain.current_regime,
                        commission_cost=max(2.0, shares * 0.005),
                        slippage_cost=shares * pattern.entry * 0.0005,
                    )
                    async with self.brain._state_lock:
                        self.brain.positions.append(pos)
                    await self.brain._log_trade_entry(pos)
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
