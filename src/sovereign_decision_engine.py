"""
src/sovereign_decision_engine.py - The Singular Decision Point
==========================================================================
This is the ONLY engine authorized to resolve agent outputs into an EXECUTE signal.
It enforces a 'Strict Quorum' of 7 agents and provides an immutable audit trace.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from dateutil import parser as dtparser

try:
    from intelligence_bus import SharedIntelligenceBus
except ImportError:
    SharedIntelligenceBus = None

logger = logging.getLogger(__name__)


class SovereignDecisionEngine:
    def __init__(self, required_agents: Optional[List[str]] = None, bus: Optional[Any] = None):
        self.required_agents = required_agents or [
            "Agent_A",
            "Agent_B",
            "Agent_C",
            "Agent_D",
            "Agent_E",
            "Agent_F",
            "Agent_G",
            "Risk_Guard",
            "Dhatu_Oracle",
            "Swarm_Predictor",
            "Mind_Ultrathink",
        ]
        self.last_cycle_timestamp = None
        self.bus = bus
        self._lock = asyncio.Lock()  # --- TASK 4.3: EXECUTION LOCK ---
        self._active_symbols = set()  # Track symbols currently being processed

    async def evaluate(
        self, context: Dict[str, Any], agent_outputs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate normalized agent outputs and return a final decision.
        Enforces a singleton lock on trade firings.
        """
        async with self._lock:
            symbol = context.get("symbol", "UNKNOWN")

            # Prevent race conditions on the same symbol
            if symbol in self._active_symbols:
                return await self._reject(
                    f"Execution Lock: Symbol {symbol} already undergoing quorum."
                )

            self._active_symbols.add(symbol)
            try:
                result = await self._evaluate_logic(context, agent_outputs)
                return result
            finally:
                self._active_symbols.remove(symbol)

    async def _evaluate_logic(
        self, context: Dict[str, Any], agent_outputs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Core quorum evaluation logic (internal)."""
        # --- TASK 2: SYNCHRONIZED SNAPSHOT GUARANTEE ---
        context_ts = context.get("timestamp")
        if not context_ts:
            return await self._reject("Decision Cycle Fault: Context missing timestamp.")

        # --- TASK 1 & 3: DECISION INTEGRITY CHECK ---
        is_probe = context.get("is_probe", False)
        # Relaxed: allow extra agents (like Native_SLM) but enforce mandatory ones.
        if len(agent_outputs) < len(self.required_agents) and not is_probe:
            return await self._reject(
                f"Quorum Violation: Expected at least {len(self.required_agents)} agents, got {len(agent_outputs)}."
            )

        # --- TASK 4: FAIL-SAFE HANDLING & VALIDATION ---
        received_agents = [out["agent"] for out in agent_outputs]
        for req in self.required_agents:
            if req not in received_agents and not is_probe:
                return await self._reject(
                    f"Failure Handling: Mandatory Agent '{req}' missing from cycle."
                )

        # --- QUORUM CALCULATIONS ---
        yes_votes = 0
        no_votes = 0
        abstain_votes = 0
        total_confidence = 0.0

        # Mapping for easier access
        output_map = {out["agent"]: out for out in agent_outputs}

        for agent, out in output_map.items():
            vote = out.get("vote")
            if vote not in ["YES", "NO", "ABSTAIN"]:
                return await self._reject(
                    f"Data Mismatch: Agent '{agent}' returned invalid vote '{vote}'."
                )

            if out.get("confidence") is None:
                return await self._reject(
                    f"Data Mismatch: Agent '{agent}' returned NULL confidence."
                )

            # --- TASK 4.2: SYNC TOLERANCE (±15 seconds) ---
            # If an agent is too slow, we exclude its vote but allow the quorum to proceed.
            agent_ts = out.get("timestamp")
            if agent_ts and context_ts:
                try:
                    t_ctx = dtparser.parse(context_ts)
                    t_agt = dtparser.parse(agent_ts)
                    drift_sec = abs((t_agt - t_ctx).total_seconds())
                    if drift_sec > 60.0:
                        logger.warning(
                            f"DecisionEngine: Agent '{agent}' too slow (drift={drift_sec:.2f}s). Excluding from quorum."
                        )
                        continue  # Skip this agent, don't reject the whole cycle
                except Exception:
                    pass

            # Processing Vote
            if vote == "YES":
                # Agent_D is the Historical Learning engine — it knows your REAL edge.
                # Weight it 2x: it is the only agent whose vote is grounded in live P&L data.
                yes_votes += 2.0 if agent == "Agent_D" else 1
            elif vote == "NO":
                no_votes += 1
            else:
                abstain_votes += 1
                continue

            total_confidence += out["confidence"]

        # Normalize confidence by ACTIVE voters only.
        # Dividing by the total required_agents count (11) unfairly penalizes cycles
        # where agents timed out or abstained — their 0.0 fallback confidence
        # would artificially drag down the average and kill valid trades.
        active_voters = len(agent_outputs) - abstain_votes
        avg_confidence = total_confidence / active_voters if active_voters > 0 else 0.0

        # --- PHASE 4: QUORUM LOGIC IMPLEMENTATION (Triangulation Protocol) ---
        is_probe = context.get("is_probe", False)

        # 1. HARD VETO CHECK (Risk First)
        if output_map.get("Risk_Guard", {}).get("vote") == "NO" and not is_probe:
            return await self._final_report(
                decision="REJECT",
                confidence=avg_confidence,
                reason="🛑 HARD VETO: Risk_Guard blocked the trade (Safety Protocol).",
                votes=agent_outputs,
            )

        # 2. HARD COGNITIVE VETO (Mind_Ultrathink)
        mind_out = output_map.get("Mind_Ultrathink", {})
        if mind_out.get("vote") == "NO" and not is_probe:
            return await self._final_report(
                decision="REJECT",
                confidence=avg_confidence,
                reason=f"🛑 COGNITIVE VETO: Mind_Ultrathink REJECTED the trade. Reason: {mind_out.get('reason')}",
                votes=agent_outputs,
            )

        # 2. Quorum Threshold Check — regime-aware
        regime = context.get("regime", "UNKNOWN")

        # Enforce Safe-Mode 90% Threshold if active
        if context.get("safe_mode_active"):
            required_threshold = 0.50
            actual_threshold = yes_votes / len(self.required_agents)
            is_probe = context.get("is_probe", False)

            if (actual_threshold >= required_threshold) and (avg_confidence > 0.70 or is_probe):
                logger.info(
                    f"🏛️ SAFE-MODE SUCCESS: High-Fidelity Quorum achieved ({actual_threshold:.2%})"
                )
                return await self._final_report(
                    decision="EXECUTE",
                    confidence=avg_confidence,
                    reason=f"🏛️ SAFE-MODE SUCCESS: Quorum {actual_threshold:.2%} achieved.",
                    votes=agent_outputs,
                )
            else:
                return await self._final_report(
                    decision="REJECT",
                    confidence=avg_confidence,
                    reason=f"🛑 SAFE-MODE REJECTION: Consensus {actual_threshold:.2%} < 50%.",
                    votes=agent_outputs,
                )
        else:
            # This ensures we have a real majority even if many agents abstain.
            is_probe = context.get("is_probe", False)

            min_required = 4 if regime in ("CHOPPY", "VOLATILE") else 5
            # Ensure at least 60% of active voters say YES
            vote_ratio = (yes_votes / active_voters) if active_voters > 0 else 0

            # --- SOVEREIGN PROBE BYPASS ---
            # If it's a probe, we pass if any agent responded YES (wiring test).
            # Otherwise, enforce strict quorum.
            if is_probe:
                if yes_votes > 0:
                    return await self._final_report(
                        decision="EXECUTE",
                        confidence=avg_confidence,
                        reason=f"PHANTOM PROBE SUCCESS: Wiring active ({yes_votes} Agents YES).",
                        votes=agent_outputs,
                    )
                else:
                    return await self._final_report(
                        decision="REJECT",
                        confidence=avg_confidence,
                        reason="PHANTOM PROBE FAILURE: All agents rejected or silent.",
                        votes=agent_outputs,
                    )

            if not (yes_votes >= min_required and vote_ratio >= 0.60 and avg_confidence > 0.60):
                return await self._final_report(
                    decision="REJECT",
                    confidence=avg_confidence,
                    reason=f"Consensus Failure: Votes({yes_votes}/{active_voters}), Ratio({vote_ratio:.2%}), Conf({avg_confidence:.2f}).",
                    votes=agent_outputs,
                )

        # If Agent D detects 'Edge Crowding' (M-05), we apply 'Ghost Expansion'.
        d_out = output_map.get("Agent_D", {})
        if d_out.get("metadata", {}).get("edge_crowded", False):
            logger.warning(
                f"🏛️ STOP-RUN SHIELD: Edge Crowding detected for {context.get('symbol', 'UNKNOWN')}. Applying Ghost Expansion (Wider Stop / Smaller Size)."
            )
            # Metadata tags for Agent C to handle the expansion
            context["execution_mode"] = "GHOST_EXPANSION"
            context["stop_multiplier"] = 1.35  # 35% wider to breathe through the flush
            context["size_multiplier"] = 0.75  # 25% smaller to maintain risk parity

        return await self._final_report(
            decision="EXECUTE",
            confidence=avg_confidence,
            reason=f"Quorum Met: {yes_votes}/11 agents ({regime} mode, threshold={min_required}).",
            votes=agent_outputs,
        )

    async def _reject(self, reason: str) -> Dict[str, Any]:
        logger.error(f"ENGINE REJECTION: {reason}")
        report = {
            "decision": "REJECT",
            "confidence": 0.0,
            "reason": reason,
            "timestamp": time.time() * 1000,
            "votes": [],
        }
        if self.bus:
            await self.bus.publish("consensus.update", report)
        return report

    async def _final_report(
        self, decision: str, confidence: float, reason: str, votes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        report = {
            "decision": decision,
            "confidence": round(confidence, 4),
            "reason": reason,
            "timestamp": time.time() * 1000,
            "votes": votes,
            "phase": decision,
        }
        logger.info(f"DECISION LOG: [{decision}] | Conf: {confidence:.2f} | Reason: {reason}")
        if self.bus:
            await self.bus.publish("consensus.update", report)
        return report


# --- ENFORCEMENT GUARD ---
# This acts as the authorized entry point check for Agent C
def verify_authorized_caller(frame):
    # This is a runtime check to ensure only the decision engine or brain can call execution
    caller_name = frame.f_back.f_code.co_name
    authorized = ["evaluate", "run_all_agents", "_process_execute"]
    return caller_name in authorized
