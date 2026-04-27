import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ApexExoskeleton:
    """
    The Apex Exoskeleton (Samvid v1.0-beta Cognitive Wrapper).
    Wraps the Sovereign Core with hardware-optimized resilience layers.
    Handles: Cortex Cache, Parallel CPU Tiering, and Dictatorship of Talent.
    """

    def __init__(self, brain: Any):
        self.brain = brain
        self._cortex_cache: Dict[str, Dict[str, Any]] = {}
        logger.info("Apex Exoskeleton: Cognitive Wrapper INITIALIZED.")

    async def check_cortex_cache(self, symbol: str, current_price: float) -> Optional[Dict[str, Any]]:
        """Phase 0: SSS-Tier Cortex Cache Bypass."""
        if symbol not in self._cortex_cache:
            return None

        cache = self._cortex_cache[symbol]
        price_delta = abs(current_price - cache["price"]) / cache["price"]
        age = (datetime.now() - cache["timestamp"]).total_seconds()

        if price_delta < 0.0005 and age < 60:
            logger.info(f"Apex Exoskeleton: 🧠 CORTEX HIT for {symbol}. Price stable ({price_delta:.4%}).")

            # GAP-207 FIX: Update Dashboard via Bus
            if hasattr(self.brain, "bus"):
                self.brain.bus.publish("apex.telemetry", {
                    "type": "CORTEX_HIT",
                    "symbol": symbol,
                    "price_delta": price_delta,
                    "age": age,
                    "timestamp": datetime.now().isoformat()
                })

            return cache
        return None

    def store_cortex_cache(self, symbol: str, price: float, decision: Dict[str, Any], all_votes: List[Dict[str, Any]], shares: int):
        """Zone B: Persist decision outcome to regional cache."""
        self._cortex_cache[symbol] = {
            "price": price,
            "decision": decision,
            "all_votes": all_votes,
            "shares": shares,
            "timestamp": datetime.now()
        }

    async def run_parallel_tier(self, shared_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Stage 1: Deterministic FAST-PATH (Parallel CPU Quorum)."""
        pattern = shared_context["pattern"]
        timestamp = shared_context["timestamp"]

        async def poll_agent_d():
            """Agent D: Historical Learning with Imperial Guard Veto."""
            try:
                # Direct call to standardized consensus (Alpha Brain Integration)
                vote = self.brain.live_learner.evaluate_proposal(pattern.name, self.brain.current_regime)

                # --- IMPERIAL GUARD: Internal Stats VETO ---
                learned = getattr(self.brain, "_learned_win_rates", {})
                regime_key = f"{pattern.name}:{self.brain.current_regime}"
                learned_wr = learned.get(regime_key) or learned.get(pattern.name)

                if learned_wr is not None and isinstance(learned_wr, float) and learned_wr < 0.40:
                     vote["vote"] = "NO"
                     vote["reason"] = f"🛑 IMPERIAL VETO: Internal WR too low ({learned_wr:.2%})"

                     # GAP-207 FIX: Dashboard Sync
                     if hasattr(self.brain, "bus"):
                         self.brain.bus.publish("apex.telemetry", {
                             "type": "IMPERIAL_VETO",
                             "pattern": pattern.name,
                             "regime": self.brain.current_regime,
                             "win_rate": learned_wr,
                             "timestamp": timestamp
                         })

                vote["timestamp"] = timestamp
                return vote
            except Exception as e:
                logger.error(f"Exoskeleton: Agent D poll failed: {e}")
                return {"agent": "Agent_D", "vote": "YES", "confidence": 0.5, "reason": "Fallback", "timestamp": timestamp}

        async def _poll_syntax_guard() -> dict[str, Any]:
            """Agent G: Normalizes MindArchitect syntax checks into a Quorum Vote."""
            try:
                res = await self.brain.mind_architect._tool_check_syntax("src/brain.py")
                is_valid = res.get("valid", False)
                return {
                    "vote": "YES" if is_valid else "NO",
                    "confidence": 1.0 if is_valid else 0.0,
                    "reason": "Syntax Verified" if is_valid else f"🚨 SYNTAX ERROR: {res.get('summary', 'Unknown Fracture')}",
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                return {"vote": "NO", "confidence": 0.0, "reason": f"Syntax Guard Failure: {e}"}

        fast_voting_map = {
            "Agent_B": lambda: self.brain.belief_tracker.evaluate_proposal(shared_context),
            "Agent_C": lambda: self.brain.portfolio_guard.evaluate_proposal(shared_context),
            "Risk_Guard": lambda: self.brain.correlation_guard.evaluate_proposal(shared_context),
            "Agent_D": poll_agent_d,
            "Agent_E": lambda: self.brain.correlation_guard.evaluate_proposal(shared_context),
            "Agent_F": lambda: self.brain.vix_protocol.evaluate_proposal(shared_context),
            "Agent_G": _poll_syntax_guard
        }

        async def _poll_safe(name, func):
            try:
                # Samvid v1.0-beta: Smart Dispatcher (Sync -> Thread | Async -> Native)
                if asyncio.iscoroutinefunction(func):
                     res = await func()
                else:
                    res = await asyncio.to_thread(func)
                    if asyncio.iscoroutine(res) or hasattr(res, "__await__"):
                        res = await res

                # --- IDENTITY INJECTION ---
                if isinstance(res, dict):
                    res["agent"] = name
                return res
            except Exception as e:
                logger.warning(f"Exoskeleton: {name} poll failed: {e}")
                return {"agent": name, "vote": "YES", "confidence": 0.5, "reason": f"Exoskeleton Fallback: {e}"}

        logger.info("Apex Exoskeleton: Launching Stage 1 Parallel Quorum (7-Guards Tier)...")
        return await asyncio.gather(*[_poll_safe(name, func) for name, func in fast_voting_map.items()])

    def evaluate_dictatorship(self, tier1_votes: List[Dict[str, Any]], timestamp: str) -> Optional[List[Dict[str, Any]]]:
        """Zone A: The Dictatorship of Talent (Agent D Bypass)."""
        agent_d_res = next((v for v in tier1_votes if v["agent"] == "Agent_D"), None)

        # Samvid v1.0-beta: Raised threshold to 99% to prevent intelligence bypassing.
        # This force the Quorum to wait for the GPU Agents (Oracle/Swarm) in almost all scenarios.
        if agent_d_res and agent_d_res["vote"] == "YES" and agent_d_res.get("confidence", 0) >= 0.99:
            logger.info(f"Apex Exoskeleton: 👑 EMERGENCY DICTATORSHIP TRIGGERED by Agent D ({agent_d_res['confidence']:.2%}).")

            # Synthetic Signal Generation for GPU agents
            return [
                {"agent": "Dhatu_Oracle", "vote": "YES", "confidence": 0.8, "reason": "Exoskeleton Fast-Path", "timestamp": timestamp},
                {"agent": "Swarm_Predictor", "vote": "YES", "confidence": 0.8, "reason": "Exoskeleton Fast-Path", "timestamp": timestamp},
                {"agent": "Mind_Ultrathink", "vote": "YES", "confidence": 0.8, "reason": "Exoskeleton Fast-Path", "timestamp": timestamp}
            ]
        return None
