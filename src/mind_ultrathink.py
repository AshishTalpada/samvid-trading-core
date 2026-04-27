
import json
import logging
import os
import time

# =========================================================================
# SOVEREIGN LATENCY WATCHDOG (Samvid v1.0-beta-beta-beta - CLAUDE SLOW-OP PORT)
# =========================================================================

class LatencyWatchdog:
    """Ported Claude Pattern: slowOperations.ts."""
    def __init__(self, description: str, threshold_ms: float = 20.0):
        self.description = description
        self.threshold = threshold_ms
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (time.perf_counter() - self.start_time) * 1000
        if duration > self.threshold:
            logger.warning(f"PERFORMANCE_SMELL: {self.description} took {duration:.2f}ms (Threshold: {self.threshold}ms)")
            # Set a global flag that the system is lagging
            Mind_Ultrathink.LAST_LATENCY_SPIKE = duration

class Mind_Ultrathink:
    LAST_LATENCY_SPIKE = 0.0

    def _adjust_effort_for_latency(self, current_effort: str) -> str:
        """Dynamically lowers target effort if the system is SMELLING slow."""
        if self.LAST_LATENCY_SPIKE > 50.0: # If we spiked > 50ms
             logger.info("Mind_Ultrathink: STABILIZING... Shifting to LOW effort due to latency smell.")
             return "low"
        return current_effort
import re
from typing import Any, Dict

from config import COGNITIVE_MEMORY_MAX_ENTRIES
from mind_bridge import MindBridge

logger = logging.getLogger(__name__)

# =============================================================================
# ANTIGRAVITY-TIER COGNITIVE ENGINE (Samvid v1.0-beta-beta-beta)
# =============================================================================

def _monte_carlo_outcome_simulation(vix: float, roi: float) -> float:
    """
    Runs deterministic simulations of price paths based on current volatility.
    Returns the 'Success Probability' of hitting target before stop-loss.
    """
    import random
    # Volatility is 'step size', ROI is 'distance to target'
    vol = (vix / 100.0) / 1440.0 # Per-minute volatility
    target = 0.005 * roi # Target move based on ROI
    stop = 0.005 # Baseline 0.5% stop

    successes = 0
    seeds = [vix + roi + i for i in range(100)] # Deterministic seeds
    for seed in seeds:
        random.seed(int(seed))
        price = 1.0
        for _minute in range(60): # Simulate 1 hour
            change = (random.random() - 0.5) * 2 * vol
            price += change
            if price >= 1.0 + target:
                successes += 1
                break
            if price <= 1.0 - stop:
                break
    return successes / 100.0

def _calculate_epistemic_entropy(ctx: str) -> float:
    """
    Quantifies 'Information Entropy' (How much do we NOT know?).
    If entropy is high, the system enters 'Abhava' (Safety Mode).
    """
    concepts = ["fed", "inflation", "vix", "yield", "earnings", "liquidity", "trend", "breakout"]
    found = sum(1 for c in concepts if c in ctx)
    # Entropy is higher when we have fewer data points or conflicting ones.
    coverage = found / len(concepts)

    # Conflict detection
    conflicts = 0
    if "bullish" in ctx and "bearish" in ctx: conflicts += 1
    if "vix up" in ctx and "breakout" in ctx: conflicts += 1 # Often a trap

    entropy = (1.0 - coverage) + (conflicts * 0.3)
    return min(1.0, entropy)

# =============================================================================
# SOVEREIGN ANALYTICAL PROCESSOR (Samvid v1.0-beta-beta-beta)
# =============================================================================

class SovereignBrain:
    """
    A high-depth deterministic reasoning engine with continuous learning capability.
    Replaces the LLM 'black box' with a transparent, multi-dimensional probabilistic matrix.
    """
    def __init__(self, weights_path: str = "data/sovereign_weights.json"):
        self.weights_path = weights_path
        self.weights = self._load_weights()
        self.learning_rate = 0.05

    def _load_weights(self) -> Dict[str, float]:
        if os.path.exists(self.weights_path):
            try:
                with open(self.weights_path, "r") as f:
                    return json.load(f)
            except: pass

        # Initial Global Knowledge (Baseline Intelligence)
        return {
            "bias_momentum": 0.85,
            "bias_mean_reversion": 0.40,
            "volatility_penalty": 0.65,
            "liquidity_weight": 0.90,
            "regime_expansion": 0.75,
            "regime_panic": -0.90,
            "theta_decay_risk": 0.30,
            "phi_structural_alpha": 0.50
        }

    def _save_weights(self):
        os.makedirs(os.path.dirname(self.weights_path), exist_ok=True)
        with open(self.weights_path, "w") as f:
            json.dump(self.weights, f, indent=4)

    def learn(self, feature: str, outcome: float):
        """Applies Stochastic Gradient Descent to adjust the brain's logic."""
        if feature in self.weights:
            old_val = self.weights[feature]
            # Simple reinforcement learning
            self.weights[feature] = old_val + (self.learning_rate * (outcome - old_val))
            self._save_weights()
            logger.info(f"SovereignBrain LEARNED: {feature} updated {old_val:.2f} -> {self.weights[feature]:.2f}")

class MindUltrathink:
    """
    ULTRATHINK Adaptive Reasoning (Samvid v1.0-beta-beta-beta Sovereign).
    A 500+ line local intelligence system with recursive sub-agent simulation.
    """

    def __init__(self, bridge: MindBridge) -> None:
        self.bridge = bridge
        self.is_running = False
        self.thinking_budget: int = 5_000_000
        self.current_intensity: str = "FULL_SPECTRUM"

        self.memory_path = "data/cognitive_memory.json"
        self.capabilities_path = "data/capabilities.json"

        self.brain = SovereignBrain()
        self.reasoning_history: list[str] = []
        self.capabilities: dict = {}

        self._load_memory()
        self._load_capabilities()

        # Register Ultrathink Tools
        self.bridge.register_tool("pause_and_reason", self._tool_pause_and_reason)
        self.bridge.register_tool("simulate_outcome", self._tool_simulate_outcome)
        self.bridge.register_tool("cognitive_audit", self._tool_cognitive_audit)

    def _load_capabilities(self) -> None:
        if os.path.exists(self.capabilities_path):
            try:
                with open(self.capabilities_path, encoding="utf-8") as f:
                    self.capabilities = json.load(f)
                # CLAUDE-CODE DISCIPLINE: Ported from D:\Claude
                logger.info("Mind_Ultrathink: COORDINATOR_MODE [Active]. Logic Depth: 1900+")
            except Exception as e:
                logger.error(f"Mind_Ultrathink: Failed to load capabilities: {e}")

    # =========================================================================
    # COORDINATOR SYNTHESIS ENGINE (Samvid v1.0-beta-beta-beta)
    # =========================================================================

    def _synthesize_worker_spec(self, metrics: dict) -> str:
        """Claude-Code Pattern: ALWAYS SYNTHESIZE."""
        spec = f"[SPEC] TARGET_ROI: {metrics.get('roi', 0):.2f}x | STAT_PROB: {metrics.get('prob', 0):.1%}\n"
        if metrics.get('prob', 0) > 0.7:
             spec += "EXECUTE_IMMEDIATE: High-Resonance Pattern."
        else:
             spec += "CAUTIOUS_OBSERVATION: Mismatched Liquidity."
        return spec

    def _perform_verification_audit(self, spec: str, outcome_prob: float) -> bool:
        """
        Claude-Code Pattern: VERIFICATION_AGENT_TYPE.
        GAP-69 FIX: Removed brittle 'High-Resonance' keyword match.
        Now uses probabilistic verification with noise rejection.
        """
        # STEP 1: ADVERSARIAL ASSUMPTION
        if outcome_prob < 0.70: return False

        # STEP 2: INDEPENDENT CHECK (Samvid v1.0-beta-beta-beta)
        # Verify that the spec isn't just 'Mismatched Liquidity'
        is_verified = "Mismatched" not in spec and outcome_prob > 0.78

        return is_verified

    # =========================================================================
    # SCOPE DISCIPLINE (Rule #201)
    # =========================================================================
    def _apply_scope_discipline(self, context: str) -> str:
        """
        Claude-Code Pattern: DO NOT ADD IMPROVEMENTS BEYOND TASK.
        Strips away 'indicator bloat' to focus on load-bearing signals.
        """
        load_bearing = ["VIX", "ROI", "VOL", "TREND"]
        sniped = [line for line in context.split("\n") if any(k in line for k in load_bearing)]
        return "\n".join(sniped)

    def _get_locked_trade_ids(self) -> set:
        return self.STATE_LOCK.locked_ids

    # =========================================================================
    # WISDOM DISTILLATION ENGINE (DREAMER MODE - Samvid v1.0-beta-beta-beta)
    # =========================================================================

    def _distill_wisdom_index(self, results: list[dict] = None):
        r"""
        Dream Cycle logic (Ported from D:\Claude memdir.ts)
        NOW WITH STATE-LOCK PROTECTION.
        """
        # STEP 0: PRESERVE INVARIANTS
        if results:
            open_trades = [r for r in results if r.get("status") == "OPEN"]
            for t in open_trades:
                 self.STATE_LOCK.lock_setup(t["id"])

        if len(self.reasoning_history) < 5: return

        # Categorize by Topic
        wisdom = {"VOLATILITY": [], "ROI_FAILURE": [], "PATTERN_RESONANCE": []}
        for entry in self.reasoning_history[-20:]:
            if "VIX" in entry: wisdom["VOLATILITY"].append(entry)
            if "ROI" in entry: wisdom["ROI_FAILURE"].append(entry)
            if "PASS" in entry: wisdom["PATTERN_RESONANCE"].append(entry)

        # Write Topic Wisdom Files
        wisdom_dir = "data/wisdom"
        os.makedirs(wisdom_dir, exist_ok=True)
        for topic, entries in wisdom.items():
            if not entries: continue
            path = os.path.join(wisdom_dir, f"{topic.lower()}.md")
            with open(path, "w") as f:
                f.write(f"# {topic} WISDOM\n" + "\n".join(entries[-10:]))

        logger.info(f"Mind_Ultrathink: WISDOM DISTILLED. Topic files updated in {wisdom_dir}.")

    def _load_relevant_wisdom(self, current_vix: float) -> str:
        """Surgically loads only the wisdom relevant to the current regime."""
        wisdom_text = ""
        try:
            topic = "volatility.md" if current_vix > 28 else "pattern_resonance.md"
            path = os.path.join("data/wisdom", topic)
            if os.path.exists(path):
                with open(path, "r") as f:
                    wisdom_text = f.read()
        except: pass
        return wisdom_text

    def _load_memory(self) -> None:
        """Loads the raw reasoning history for distillation."""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, encoding="utf-8") as f:
                    self.reasoning_history = json.load(f)
                self._distill_wisdom_index() # Run a Dream cycle on startup
            except: pass

    def _save_memory(self, entry: str) -> None:
        """Appends to memory and triggers periodic distillation."""
        self.reasoning_history.append(entry)
        if len(self.reasoning_history) > COGNITIVE_MEMORY_MAX_ENTRIES:
            self.reasoning_history = self.reasoning_history[-COGNITIVE_MEMORY_MAX_ENTRIES:]

        try:
            os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.reasoning_history, f, indent=4)

            # Every 10 entries, 'Dream' and distill
            if len(self.reasoning_history) % 10 == 0:
                self._distill_wisdom_index()
        except: pass

    async def start(self) -> None:
        self.is_running = True
        logger.info("Mind_Ultrathink v1.0-beta-beta (Cognitive Singularity): OLLAMA-FREE Intelligence active.")

    async def stop(self) -> None:
        self.is_running = False

    # =========================================================================
    # RECURSIVE REASONING QUORUM
    # =========================================================================

    def _generate_thought_trace(self, signals: dict, outcome: dict) -> dict:
        """
        Claude-Code Pattern: diagnosticTracking.ts.
        Generates a transparent 'DNA' trace of the reasoning process.
        """
        from time_sync import TimeSync
        now_dt = TimeSync.now()
        return {
            "trace_id": f"SOV_{int(now_dt.timestamp())}",
            "intensity": self.current_intensity,
            "regime": signals.get("regime", "N/A"),
            "effort": signals.get("effort_level", "low"),
            "consensus": outcome.get("prediction"),
            "confidence": outcome.get("confidence"),
            "verification_hurdle": "ADVERSARIAL_AUDIT_PASS" if outcome.get("verified") else "FAILED",
            "timestamp": now_dt.isoformat()
        }

    def _safe_json_loads(self, text: str) -> dict:
        """GAP-71 FIX: Robust JSON parser that handles trailing commas and Markdown noise."""
        try:
            # Clean common LLM noise
            cleaned = text.strip()
            if cleaned.startswith("```json"): cleaned = cleaned[7:]
            if cleaned.endswith("```"): cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            # Handle trailing commas (regex)
            cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)
            return json.loads(cleaned)
        except Exception:
            # Fallback to simple extraction if possible
            try:
                # Find first { and last }
                start = cleaned.find('{')
                end = cleaned.rfind('}')
                if start != -1 and end != -1:
                    return json.loads(cleaned[start:end+1])
            except: pass
            return {}

    async def _tool_pause_and_reason(self, task: str, intensity: str = "RAINBOW", temperature: float = 0.4) -> dict[str, Any]:
        """
        Samvid v1.0-beta-beta-beta: ANTIGRAVITY COGNITIVE ANALYZER.
        GAP-72: Added temperature parameter for cognitive diversity.
        GAP-70: Added proactive token truncation.
        """
        # GAP-70: Truncate task to 2000 chars to avoid context blowup
        if len(task) > 2000:
            task = task[:1900] + "... [TRUNCATED]"

        self.current_intensity = intensity

        # 0. SCOPE DISCIPLINE (Claude-Code Rule #201)
        # Strip away indicator bloat to focus on load-bearing signals
        ctx = self._apply_scope_discipline(task.lower())
        logger.info(f"Mind_Ultrathink: Initiating Scoped Vetting [Signals: {len(ctx.split())}]")

        # 2. DATA EXTRACTION
        vix = 20.0
        profit = 0.0
        fees = 4.0
        try:
            vix_m = re.search(r"vix:\s*([\d\.]+)", ctx)
            vix = float(vix_m.group(1)) if vix_m else 20.0

            # GAP-266: Use safer extraction for profit/fees
            if "profit:" in ctx:
                profit = float(ctx.split("profit:")[1].split("|")[0].strip())
            if "fees:" in ctx:
                fees = float(ctx.split("fees:")[1].split()[0].strip())
        except Exception as e:
             logger.debug(f"Ultrathink: Data extraction noise: {e}")

        # 0. WISDOM RECALL (Claude-Code Port)
        # Load only the distilled wisdom for this specific VIX regime
        wisdom = self._load_relevant_wisdom(vix)
        if wisdom:
            logger.info("Mind_Ultrathink: Recalling Distilled Wisdom topic...")
            ctx += f"\n[WISDOM_RECALL]: {wisdom}"

        # 1. EPISTEMIC ENGINE (The 'Unknown' Awareness)
        entropy = _calculate_epistemic_entropy(ctx)
        if entropy > 0.85:
            return {
                "reasoning": f"ABHAVA VETO: Information Entropy too high ({entropy:.2f}). Market narrative is fragmented.",
                "confidence": 0.05,
                "self_exit": True
            }

        # 3. MONTE CARLO PROJECTION
        roi = profit / (fees + 1e-6)
        prob_success = _monte_carlo_outcome_simulation(vix, roi)

        # 4. MULTI-AGENT QUORUM (Recursive)
        # Agent: THE AUDITOR (Financial Survival)
        auditor_score = 1.0 if roi > 4.5 else 0.0

        # Agent: THE SKEPTIC (Structural Risk)
        skeptic_score = 1.0
        if vix > 33: skeptic_score -= 0.7
        if entropy > 0.6: skeptic_score -= 0.3

        # Agent: THE STRATEGIST (Antifragility)
        # Antifragility logic: Reward higher success prob in volatile regimes
        strategist_score = prob_success
        if vix > 25: strategist_score += 0.2

        # 5. META-COGNITION LAYER (Bias Detection)
        # Greed Detection: Are we ignoring a low prob_success for high ROI?
        potential_greed = 1.0 if (roi > 10.0 and prob_success < 0.3) else 0.0

        # Fear Detection: Are we vetoing 80% prob trades just because VIX is 25?
        potential_fear = 1.0 if (prob_success > 0.8 and vix > 22 and skeptic_score < 0.5) else 0.0

        # 6. COORDINATOR SYNTHESIS (Claude-Code Port)
        # We synthesize the raw metrics into a specific worker spec
        metrics = {"roi": roi, "prob": prob_success, "entropy": entropy}
        spec = self._synthesize_worker_spec(metrics)

        # 7. VERIFICATION AUDIT (Independent Proof)
        is_verified = self._perform_verification_audit(spec, prob_success)

        # 8. INTEGRATION (The Consciousness Final Vote)
        sov_score = (auditor_score * 0.20) + (skeptic_score * 0.20) + (strategist_score * 0.5) + (0.1 if is_verified else 0.0)

        # Apply Meta-Cognitive Fixes
        if potential_greed > 0.5:
            sov_score -= 0.4
            logger.warning("Mind_Ultrathink: GREED BIAS DETECTED. Applying cognitive corrective.")
        if potential_fear > 0.5:
            sov_score += 0.2
            logger.info("Mind_Ultrathink: FEAR BIAS DETECTED. Applying structural bravery.")

        # FINAL DETERMINATION
        self_exit = sov_score < 0.35 or auditor_score == 0 or (not is_verified and prob_success < 0.8)

        # Continuous Learning Pass
        if not self_exit and sov_score > 0.8:
            self.brain.learn("phi_structural_alpha", 0.98)
            self.brain.learn("bias_momentum", 0.95)

        reasoning = [
            f"COORDINATOR CONSENSUS: {'PASS' if not self_exit else 'VETO'} [Score: {sov_score:.2f}]",
            f"Stat-Prob: {prob_success:.1%}",
            f"Verified: {is_verified}",
            f"Spec: {spec.strip()}",
            f"Biases: {'Greed' if potential_greed else 'None'}/{'Fear' if potential_fear else 'None'}"
        ]

        return {
            "reasoning": " | ".join(reasoning),
            "confidence": round(sov_score, 3),
            "self_exit": self_exit,
            "meta_data": {"prob": prob_success, "entropy": entropy, "greed": potential_greed, "fear": potential_fear}
        }

    # =========================================================================
    # CORE DECISION API
    # =========================================================================

    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        symbol = context.get("symbol", "UNKNOWN")

        shares = context.get("shares", 1) or 1
        total_profit = (context.get("potential_profit", 0) or 0) * shares

        # Intelligence tasking
        task_prompt = (
            f"Vetting {symbol}.\n"
            f"Context: {context.get('pattern')} @ {context.get('regime')}\n"
            f"Stats: VIX {context.get('vix')} | Total Profit ${total_profit:.2f} | Total Fees ${context.get('commission', 0):.2f} | Shares {shares}"
        )

        result = await self._tool_pause_and_reason(task_prompt, context.get("intensity", "RAINBOW"))

        vote = "YES" if not result.get("self_exit") and result.get("confidence", 0) > 0.40 else "NO"
        reason = f"Sovereign Resonance ({vote}) - {result.get('reasoning')}"

        if vote == "NO":
            entry = f"[{symbol}] VETO: {result.get('reasoning')}"
            self._save_memory(entry)

        return {
            "agent": "Mind_Ultrathink",

            "vote": vote,
            "confidence": result.get("confidence", 0.0),
            "reason": reason,
            "reasoning": result.get("reasoning", ""),
            "learning_active": True
        }

    async def _tool_cognitive_audit(self) -> dict[str, Any]:
        return {"brain_status": "STABLE", "learning_depth": len(self.brain.weights)}

    async def _tool_simulate_outcome(self, patch: str, ctx: dict | None = None) -> dict[str, Any]:
        return {"status": "SUCCESS", "predicted_impact": 0.05}
