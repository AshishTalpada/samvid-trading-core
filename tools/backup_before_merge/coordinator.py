import asyncio
import inspect
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd
from dateutil import parser as dtparser

from resilience_layer import ApexExoskeleton

if TYPE_CHECKING:
    from brain import TradingBrain
    from mind_bridge import MindBridge

from agent_a import agent_a_validate_trade
from telegram_alerts import send_telegram_alert

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 3
# attaching to the wrong event loop when imported at module level.
from config import COMMISSION_PER_ROUND_TRIP


class TradingCoordinator:
    """
    The Central Nexus of the Sovereign Quorum.
    Orchestrates the vetting, execution, and post-mortem analysis of trade proposals.
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
        self._pending_vets: Any = set()
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
                task.log(f"PHASE_RR: Analyzing Risk/Reward for {symbol}. Pattern: {pattern.name}")
            balance = await self.brain.get_safe_buying_power("ibkr")
            from config import USD_CAD_RATE

            if balance is None or balance <= 0:
                logger.warning(f"Coordinator [{symbol}] 🛑 CAPITAL VETO: Insufficient or unavailable buying power.")
                return False

            balance_usd = balance / USD_CAD_RATE

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
                        f"Coordinator [{symbol}] 🛑 FRICTION VETO: Net RR {real_rr:.2f} is < {threshold}."
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
        if symbol in self._pending_vets:
            logger.debug(f"Coordinator: Skipping redundant vet for {symbol} (already in progress).")
            return False

        self._pending_vets.add(symbol)

        try:
            cache = await self.exoskeleton.check_cortex_cache(symbol, proposal["pattern"].entry)
            if cache and not is_probe:
                if task:
                    task.log(f"CORTEX_HIT: Re-using cached consensus for {symbol}.")
                res = await self._execute_decision(
                    symbol,
                    cache["decision"],
                    proposal["pattern"],
                    cache["all_votes"],
                    is_probe,
                )
                return res


            has_position = any(getattr(p, "symbol", None) == symbol for p in self.brain.positions)
            if has_position:
                if task:
                    task.log(f"REDUNDANCY_VETO: Position already active for {symbol}.")
                return False

            if self._semaphore is None:
                self._semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
            async with self._semaphore:
                async def _poll_safe(name, func):
                    """Imperial Dispatcher (Sync -> Thread | Async -> Native)"""
                    try:
                        if inspect.iscoroutinefunction(func):
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
                            "vote": "YES",
                            "confidence": 0.5,
                            "reason": "Fallback",
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

                if not self.brain.skill_tree.is_unlocked("vetting"):
                    logger.warning(
                        "Coordinator: Skill 'vetting' is LOCKED. Matrix is in Training Mode."
                    )
                    return False

                if self.brain.dms:
                    self.brain.dms.record_heartbeat("COORDINATOR")

                timestamp = datetime.now(timezone.utc).isoformat()
                account_value = await self.brain.get_safe_buying_power(self.brain.active_broker.lower())
                pattern = proposal["pattern"]

                alpha_val = proposal.get("lambda", pattern.confidence / 100.0)

                # Fetch OHLCV early to support Impact Oracle and Agent A
                ohlcv_1m = await self.brain._fetch_ohlcv(symbol)
                if (
                    ohlcv_1m is None or isinstance(ohlcv_1m, str) or len(ohlcv_1m) < 20
                ) and not is_probe:
                    logger.warning(
                        f"Coordinator [{proposal_id}] 🛑 DATA VETO: Insufficient OHLCV for {symbol}."
                    )
                    return False

                # Fetch spread for sizing
                spread_data = await self.brain.get_current_spread(symbol)

                # Sizing Calculation for Context
                # For probes: skip the sizer entirely — it will return 0 shares with no live data.
                # A probe is a wiring test, not a real order, so shares=1 is sufficient to pass guards.

                # --- PHASE 1: DETERMINISTIC MATH VETO (Before Sizing) ---
                # We audit the trade geometry before calculating shares to ensure we don't
                # waste resources on mathematically unsound trades.
                if not is_probe:
                    math_val = await self.brain.mind_math._tool_validate_geometry(
                        direction=("LONG" if pattern.entry > pattern.stop else "SHORT"),
                        entry_price=pattern.entry,
                        stop_price=pattern.stop,
                        target_price=pattern.target,
                        atr=getattr(pattern, "atr", 0.0),
                    )
                    if not math_val["valid"]:
                        logger.warning(
                            f"Coordinator [{proposal_id}] 🛑 MATH VETO: {math_val['reason']}"
                        )
                        return False

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
                    shares = self.brain.mt5_sizer.calculate_lots(  # type: ignore
                        risk_per_trade, pattern.entry, pattern.stop, symbol
                    ) or 0.0
                    pos_value = shares * 100000.0  # Synthetic estimate for Forex tracking
                else:
                    sizing = self.brain.ibkr_sizer.calculate(
                        win_prob=float(alpha_val or 0.5),
                        r_r_ratio=float(pattern.r_r_ratio),
                        balance=account_value or 500.0,
                        account_value=account_value or 500.0,
                        entry_price=float(pattern.entry),
                        stop_price=float(pattern.stop),
                        target_price=float(pattern.target),
                        spread=spread_data["spread"],
                        instrument=symbol,
                        ohlcv_df=ohlcv_for_sizing,
                        regime=self.brain.current_regime,
                        regime_modifier=self.brain.regime_classifier.get_risk_modifier(
                            self.brain.current_regime
                        ),
                        drawdown_modifier=self.brain.ibkr_drawdown.get_size_modifier(),
                        loss_tracker_modifier=self.brain.loss_tracker.get_size_modifier(),
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
                        "brain": self.brain,
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
                        "potential_profit": abs(float(pattern.target) - float(pattern.entry)),
                        "commission": max(COMMISSION_PER_ROUND_TRIP, (shares or 1) * 0.01),
                    }

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
                                        f"Coordinator [{proposal_id}] 🛑 QUANT VETO: {q_gate['reason']}"
                                    )
                                    return False
                    except Exception as qe:
                        logger.warning(f"Coordinator: QuantGate logic error: {qe}")

                    if self.brain.mode != "paper":
                        try:
                            cushion = await self.brain.get_ibkr_cushion()
                            if cushion < 0.15:
                                logger.critical(
                                    f"Coordinator [{proposal_id}] 🛡️ MARGIN SHIELD VETO: Cushion is too low ({cushion:.2%}). Standing down."
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
                                    "risk_flag": False,
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
                                    bid=float(cast(Any, ohlcv_1m["low"][-1])),
                                    ask=float(cast(Any, ohlcv_1m["high"][-1])),
                                    volume=float(cast(Any, ohlcv_1m["volume"][-1])),
                                )
                                if self.brain.dhatu_oracle
                                else 0.0
                            )

                            # Calculate entropy using the brain's calc
                            p_before = 0.5
                            p_after = pattern.confidence / 100.0
                            entropy_score = self.brain.entropy_calc.signal_entropy(p_before, p_after)

                            closes = ohlcv_1m["close"].to_numpy()
                            resistances = [float(np.percentile(cast(Any, closes), 90)), float(np.max(cast(Any, closes)))]
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
                                df_h1 = cast(pd.DataFrame, df_h1)
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
                            high = ohlcv_1m["high"].to_numpy()
                            low = ohlcv_1m["low"].to_numpy()
                            close = ohlcv_1m["close"].to_numpy()
                            prev_close = ohlcv_1m["close"].shift(1).to_numpy()

                            tr = np.maximum(
                                np.abs(high - low),
                                np.maximum(
                                    np.abs(high - prev_close),
                                    np.abs(low - prev_close),
                                ),
                            )
                            atr_20 = float(np.nanmean(tr[-20:]))

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
                                    float(cast(Any, ohlcv_1m["volume"][-1])) > float(cast(Any, ohlcv_1m["volume"][-20:-1].mean())) * 2.0
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
                            f"Coordinator [{proposal_id}] 🛑 SOVEREIGN VETO: Agent A rejected proposal. {agent_a_out.get('reason')}"
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

                    # --- LIVE QUORUM STREAM (Agent A Progress) ---
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

                            # --- IMPERIAL GUARD: Internal Stats VETO ---
                            if (
                                learned_wr is not None
                                and isinstance(learned_wr, float)
                                and learned_wr < 0.40
                            ):
                                agent_d_vote["vote"] = "NO"
                                agent_d_vote["reason"] = (
                                    f"🛑 IMPERIAL VETO: Internal WR too low ({learned_wr:.2%})"
                                )

                            return agent_d_vote
                        except Exception as e:
                            logger.error(f"Coordinator: Agent D poll failed: {e}")
                            return {
                                "agent": "Agent_D",
                                "vote": "YES",
                                "confidence": 0.5,
                                "reason": f"Fallback: {str(e)[:50]}",
                                "timestamp": timestamp,
                            }

                    async def poll_oracle():
                        """Dhatu Oracle: (SOLUTION 5) Uses Background State with High-Fidelity Fallback."""
                        state = self.brain.conviction_state.get("Dhatu_Oracle")
                        if (
                            state
                            and (
                                datetime.now(timezone.utc) - dtparser.parse(state["timestamp"])
                            ).total_seconds()
                            < 90
                        ):
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
                                "vote": "YES",
                                "confidence": 0.5,
                                "reason": "Oracle Offline (Deferred to Quorum)",
                                "timestamp": timestamp,
                            }

                    async def poll_swarm():
                        """Swarm Predictor: (SOLUTION 5) Uses Background State with High-Fidelity Fallback."""
                        state = self.brain.conviction_state.get("Swarm_Predictor")
                        if (
                            state
                            and (
                                datetime.now(timezone.utc) - dtparser.parse(state["timestamp"])
                            ).total_seconds()
                            < 90
                        ):
                            return state

                        try:
                            if self.brain.swarm_predictor is None:
                                raise RuntimeError("SwarmPredictor not configured")
                            logger.info(
                                "Coordinator: Background Swarm stale. Falling back to Live Collective Intelligence..."
                            )
                            return await self.brain.swarm_predictor.evaluate_proposal(shared_context)
                        except Exception as e:
                            logger.warning(f"Coordinator: Swarm Live Fallback failed: {e}")
                            return {
                                "agent": "Swarm_Predictor",
                                "vote": "YES",
                                "confidence": 0.5,
                                "reason": "Swarm Offline (Deferred to Quorum)",
                                "timestamp": timestamp,
                            }

                    # -- QUORUM ASSEMBLY (STRICT UNIQUENESS) --
                    vote_registry: Dict[str, Dict[str, Any]] = {}

                    try:
                        tier1_results = await self.exoskeleton.run_parallel_tier(shared_context)
                        for res in tier1_results:
                            if res and "agent" in res:
                                vote_registry[cast(str, res["agent"])] = res

                        dummy_tail = self.exoskeleton.evaluate_dictatorship(tier1_results, timestamp)
                        if dummy_tail:
                            for res in dummy_tail:
                                vote_registry[cast(str, res["agent"])] = res
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
                            if v.get("agent") in ["Agent_B", "Agent_C", "Risk_Guard", "Agent_E", "Agent_F", "Agent_G"]
                        )
                        if deterministic_deny and not is_probe:
                            logger.warning(
                                f"Coordinator [{proposal_id}] 🛑 EARLY EXIT: Tier 1 agents rejected. Standing down."
                            )
                            dummy_tail = [
                                {"agent": "Dhatu_Oracle", "vote": "NO", "confidence": 0.0, "reason": "Skipped", "timestamp": timestamp},
                                {"agent": "Swarm_Predictor", "vote": "NO", "confidence": 0.0, "reason": "Skipped", "timestamp": timestamp},
                                {"agent": "Mind_Ultrathink", "vote": "NO", "confidence": 0.0, "reason": "Skipped", "timestamp": timestamp},
                            ]
                            for res in dummy_tail:
                                vote_registry[str(res["agent"])] = res

                    # --- STAGE 1 TELEMETRY ---
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
                        gated_agents = []
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

                            if self.brain.native_slm and self.brain.native_slm.is_available:
                                gated_agents.append(
                                    (
                                        "Native_SLM",
                                        lambda: self.brain.native_slm.evaluate_proposal(shared_context),
                                    )
                                )

                            vram_pct = 0  # LLM purged — no VRAM contention

                            gated_votes = []
                            background_success = True
                            for name, _ in gated_agents:
                                state = self.brain.conviction_state.get(name)
                                state_ts = state.get("timestamp") if state else None
                                if (
                                    not state
                                    or not state_ts
                                    or (
                                        datetime.now(timezone.utc) - dtparser.parse(state_ts)
                                    ).total_seconds()
                                    > 90
                                ):
                                    background_success = False
                                    break
                                state["timestamp"] = timestamp
                                gated_votes.append(state)

                            if not background_success:
                                logger.warning(
                                    "Coordinator: Background Conviction Stale/Missing. Reverting to Parallel Neural Gate..."
                                )

                                # Uses _poll_neural_safe to manage VRAM contention serialy but gathered in parallel.
                                names = [n for n, _ in gated_agents]
                                funcs = [f for _, f in gated_agents]

                                results = await asyncio.gather(
                                    *[
                                        asyncio.wait_for(_poll_neural_safe(name, func), timeout=25.0)
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
                                                "vote": "YES",
                                                "confidence": 0.4,
                                                "reason": "Latency/Error Fallback",
                                            }
                                        )
                                    else:
                                        gated_votes.append(res)

                            for res in gated_votes:
                                if res and "agent" in res:
                                    vote_registry[cast(str, res["agent"])] = res
                                    # Update Conviction State for caching
                                    if res.get("confidence", 0) > 0:
                                        self.brain.conviction_state[res["agent"]] = res
                        except Exception as gated_e:
                            logger.error(f"Coordinator: Gated Intelligence failure: {gated_e}")
                            for name, _ in gated_agents:
                                err_vote = {
                                    "agent": name,
                                    "vote": "YES",
                                    "confidence": 0.5,
                                    "timestamp": timestamp,
                                }
                                vote_registry[cast(str, name)] = err_vote  # type: ignore

                    # --- STAGE 2 TELEMETRY ---
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

                    # Force the Skeptic Mind to challenge the consensus before final engine evaluation.
                    skeptic_audit = self.brain.skeptic.run_adversarial_debate(
                        proposal=agent_a_out, # Challenge the primary signal generator
                        opponents=[v["agent"] for v in all_votes if v["vote"] == "YES"]
                    )
                    all_votes.append(skeptic_audit)

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
            proposal_id = all_votes[0].get("proposal_id", "CACHE")

            if decision["decision"] == "EXECUTE":
                if is_probe:
                    if task:
                        task.log(
                            "EXECUTION_PHANTOM: System verified operational. Standing down (Probe Mode)."
                        )
                    logger.info(
                        f"Coordinator [{proposal_id}] ✅ PHANTOM PROBE SUCCESS: System wiring is 100% OPERATIONAL."
                    )
                    return True

                if task:
                    task.log(
                        f"EXECUTION_START: Routing {shares} shares to {self.brain.active_broker}."
                    )
                logger.info(f"Coordinator [{proposal_id}] [QUORUM_OK] Executing trade for {symbol}")

                is_long = pattern.entry > pattern.stop
                order_side = "BUY" if is_long else "SELL"
                urgency = "HIGH" if self.brain.current_regime in ["VOLATILE", "TRENDING"] else "LOW"

                if self.brain.active_broker == "MAINTENANCE":
                    if task:
                        task.log("MAINTENANCE_VETO: Market rollover detected. Aborting.")
                    logger.warning(
                        f"Coordinator [{proposal_id}] 🛡️ MAINTENANCE STAND-DOWN: Market rollover in progress. Order skipped."
                    )
                    return False

                # Execution with SE-11 Brackets & Ghost Expansion
                order_id = None
                if self.brain.active_broker == "IBKR":
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
                        f"🚀 *EXECUTION: {symbol}*\n"
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
                        catalyst_score=all_votes[0].get("confidence", 0.5) * 100,
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
                        task.log("EXECUTION_FAILURE: Order rejected by broker.")
                        task.finalize("FAILED")
                    if shares < 1:
                        logger.warning(
                            f"Coordinator [{proposal_id}] 🛑 SOVEREIGN STANDDOWN: Order for {symbol} blocked (Zero Size)."
                        )
                        await send_telegram_alert(
                            f"🏛️ *STANDDOWN: {symbol}*\n"
                            f"Reason: ZERO SIZE (Risk Control)\n"
                            f"ID: {proposal_id}"
                        )
                    else:
                        logger.error(
                            f"Coordinator [{proposal_id}] ❌ EXECUTION FAILURE: Order for {symbol} rejected by broker."
                        )
                        await send_telegram_alert(
                            f"🚨 *EXECUTION FAILURE: {symbol}*\n"
                            f"Reason: Broker Rejected (Check TWS/Gateway logs)\n"
                            f"ID: {proposal_id}"
                        )
                    return False
            else:
                reason = decision.get("reason", "Consensus No")
                logger.info(
                    f"Coordinator [{proposal_id}] 🛡️ VETO: {symbol} rejected by decision engine. Reason: {reason}"
                )

                await send_telegram_alert(
                    f"🛡️ *VETO: {symbol}*\nReason: {reason}\nID: {proposal_id}"
                )

                # Log the rejected proposal as a 'Shadow Trade' for post-mortem calibration.
                self.brain.shadow_sim.fork_signal(
                    symbol=symbol,
                    price=pattern.entry,
                    side=("BUY" if pattern.entry > pattern.stop else "SELL")
                )

                try:
                    from system_types import Position

                    shadow_pos = Position(
                        symbol=symbol,
                        qty=shares if shares > 0 else 0,
                        entry_price=pattern.entry,
                        entry_time=datetime.now(timezone.utc),
                        pattern=pattern.name,
                        initial_belief=0.0,  # Shadow trade has no belief
                        current_belief=0.0,
                        initial_stop=pattern.stop,
                        stop_loss=pattern.stop,
                        take_profit=pattern.target,
                        trade_id=f"SHADOW_{proposal_id}",
                        task_id=task.id if task else "N/A",
                        status="SHADOW_REJECTED",
                        meta={"reason": reason, "votes": all_votes},
                    )
                    # We only log to DB, don't add to brain.positions (not a real trade)
                    await self.brain._log_trade_entry(shadow_pos)
                except Exception as shadow_e:
                    logger.debug(f"Shadow Trade Logging failed: {shadow_e}")

                if task:
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
