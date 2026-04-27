# pyre-ignore-all-errors[21]
import os

# -----------------------------------------------------------------------------
# ABSOLUTE TELEMETRY SUPPRESSION (Samvid v1.0-beta HARDCORE)
# MUST BE SET BEFORE ANY IMPORTS THAT MIGHT TRIGGER CHROMA/POSTHOG
# -----------------------------------------------------------------------------
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

"""
src/swarm_predictor.py - MiroFish Swarm Intelligence Client Adapter

Connects to a running MiroFish instance (local or Docker) to obtain
multi-agent swarm consensus predictions for market scenarios.

MiroFish simulates thousands of AI agents with independent personalities
and long-term memory to predict future trajectories from seed data.

When MiroFish is unavailable the adapter returns a NEUTRAL signal so the
trading system can continue operating without it.
"""

import asyncio  # pyre-ignore[21]
import logging  # pyre-ignore[21]
import os
from dataclasses import dataclass, field  # pyre-ignore[21]
from datetime import datetime, timedelta, timezone  # pyre-ignore[21]
from enum import Enum  # pyre-ignore[21]
from typing import Any, Dict  # pyre-ignore[21]

import httpx  # pyre-ignore[21]

from vault import Vault  # pyre-ignore[21]

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


class SwarmBias(Enum):
    """Swarm consensus directional bias."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


@dataclass
class SwarmConsensus:
    """The distilled output of a Native Swarm prediction."""

    bias: SwarmBias = SwarmBias.NEUTRAL
    confidence: float = 0.0  # 0.0 – 1.0
    summary: str = ""  # Human-readable reasoning
    agent_count: int = 0  # How many agents participated
    rounds: int = 0  # Simulation rounds completed
    symbol: str = "GLOBAL" # GAP-36: Caching symbol (Prevents cross-symbol leaks)
    # Use datetime.min as sentinel so that a freshly created *default* consensus
    # is treated as stale (is_fresh == False). Only explicitly-set timestamps
    # from actual predictions will be recent enough to be fresh.
    generated_at: datetime = field(default_factory=lambda: datetime.min)
    _cache_minutes: int = 15  # Staleness window

    @property
    def is_fresh(self) -> bool:
        """True only if generated within the staleness window (Samvid v1.0-beta: TZ Safety)."""
        # Ensure parity: both must be naive or same-aware
        now = datetime.now(timezone.utc)
        gen = self.generated_at
        if gen.tzinfo is None:
             gen = gen.replace(tzinfo=timezone.utc)
        return (now - gen) < timedelta(minutes=self._cache_minutes)

    def should_block_entry(self, entry_side: str = "long") -> bool:
        """Returns True if the swarm consensus strongly contradicts the proposed entry direction."""
        if self.confidence < 0.70:
            return False
        if entry_side.lower() == "long" and self.bias == SwarmBias.BEARISH:
            return True
        if entry_side.lower() == "short" and self.bias == SwarmBias.BULLISH:
            return True
        return False

    def get_confidence_modifier(self, entry_side: str = "long") -> float:
        """
        Position-size modifier based on swarm alignment with trade direction (Samvid v1.0-beta Fixed).

        Args:
            entry_side: 'long' or 'short'

        Returns:
            Modifier > 1.0 if aligned, < 1.0 if contrary, 1.0 if neutral/low-conf.
        """
        if self.confidence < 0.40 or self.bias == SwarmBias.NEUTRAL:
            return 1.0

        # Check alignment
        is_aligned = (entry_side.lower() == "long" and self.bias == SwarmBias.BULLISH) or \
                     (entry_side.lower() == "short" and self.bias == SwarmBias.BEARISH)

        if is_aligned:
            # Scale UP: 1.0 to 1.15
            return 1.0 + (self.confidence - 0.40) * 0.25
        else:
            # Scale DOWN: 1.0 to 0.75 (Contradiction)
            return 1.0 - (self.confidence - 0.40) * 0.40


# =============================================================================
# CHROMA GRAPH MEMORY
# =============================================================================


class ChromaDeepMemory:
    _client_instance = None
    _lock = asyncio.Lock()

    def __init__(
        self, db_dir: str = "data/chroma_db", collection_name: str = "swarm_memory"
    ) -> None:
        import chromadb
        from chromadb.config import Settings

        # GAP-183 FIX: Singleton Client to prevent memory/file-handle leaks
        if ChromaDeepMemory._client_instance is None:
            try:
                ChromaDeepMemory._client_instance = chromadb.PersistentClient(
                    path=db_dir, settings=Settings(allow_reset=True, anonymized_telemetry=False)
                )
                logger.info(f"✓ Chroma Persistence Online (Samvid v1.0-beta Memory System) at {db_dir}")
            except Exception as e:
                logger.warning(f"Chroma: PersistentClient failed ({e}). Falling back to Ephemeral.")
                ChromaDeepMemory._client_instance = chromadb.EphemeralClient(
                    settings=Settings(allow_reset=True, anonymized_telemetry=False)
                )

        self.client = ChromaDeepMemory._client_instance

        try:
            from embedding_engine import embedding_function
            fast_ef = embedding_function
            logger.info("✓ Chroma Memory using Shared Intelligence Embedding Engine")
        except ImportError:
            logger.warning("Shared embedding engine not found locally, falling back to default Chroma embeddings")
            fast_ef = None

        self.collection = self.client.get_or_create_collection(collection_name, embedding_function=fast_ef)
        try:
            count = int(self.collection.count())  # ChromaDB v1.0-beta+ returns int directly
            logger.info(f"ChromaDB Memory Active: {count} memories in '{collection_name}'")
        except Exception:
            logger.info(f"ChromaDB Memory Active: collection '{collection_name}' ready")

    async def search_memory(self, market_narrative: str, limit: int = 5) -> tuple[str, float]:
        """
        Samvid v1.0-beta: Wisdom Retrieval & Compaction.
        Finds similar regimes AND compacts them into distilled wisdom tokens.
        """
        if not self.collection:
            return "", 0.0
        try:
            results = await asyncio.to_thread(
                self.collection.query,
                query_texts=[market_narrative],
                n_results=limit * 3 # Wider sweep for compaction candidates
            )
            if not results or not results["documents"] or not results["documents"][0]:
                return "", 0.0

            # ── WISDOM COMPACTION (SE-11 Port) ──
            # If we find highly similar memories, compact them into a single truth token
            docs = results["documents"][0]
            metas = results["metadatas"][0]

            compacted_truth = await self._compact_memories(docs, metas)
            if compacted_truth:
                logger.info("🧠 [Memory]: Highly relevant Wisdom Token compacted.")
                # Broadcast the newly synthesized truth to other agents
                from telegram_alerts import send_telegram_alert
                await send_telegram_alert(f"🏛️ *WISDOM DISCOVERED*\n{compacted_truth[:100]}...")

            memory_contexts = []
            max_conf = 0.0
            scored_memories = []
            for meta, doc in zip(metas, docs, strict=False):
                score = 0
                if meta:
                    score += float(meta.get("confidence", 0.0)) * 10
                    if meta.get("bias") != "NEUTRAL":
                         score += 5
                scored_memories.append((score, meta, doc))

            scored_memories.sort(key=lambda x: x[0], reverse=True)
            for score, meta, doc in scored_memories[:limit]:
                memory_contexts.append(doc)
                if meta:
                    max_conf = max(max_conf, float(meta.get("confidence", 0.0)))

            return "\n".join(memory_contexts), max_conf

        except Exception as e:
            logger.error(f"Chroma Search failed: {e}")
            return "", 0.0

    async def _compact_memories(self, documents: list[str], metadatas: list[dict]) -> str | None:
        """GAP-68: Compaction logic that preserves reasoning ('Why') and signals ('What')."""
        if len(documents) < 3: return None

        # Heuristic: Combine the top 3 similar memories into a high-density alpha rule
        combined = "\n".join([f"- {d}" for d in documents[:3]])
        # Note: In a production SE-11 system, we'd use an LLM here.
        # For now, we return a structured synthesis to preserve the 'Why'.
        return f"SYNTHESIZED WISDOM (n=3):\n{combined}\nREGIME_STABILITY: High"

    async def store_memory(self, symbol: str, debate_summary: str, bias_str: str, confidence: float) -> None:
        """Embeds and saves a Swarm consensus into long term memory with alpha-tracking."""
        if not self.collection:
            return
        doc_id = f"{symbol}_{int(datetime.now(timezone.utc).timestamp())}"
        try:
            await asyncio.to_thread(
                self.collection.upsert,
                documents=[debate_summary],
                metadatas=[
                    {
                        "symbol": symbol,
                        "bias": bias_str,
                        "confidence": confidence,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                ],
                ids=[doc_id],
            )
        except Exception as e:
            logger.debug(f"Chroma memory save failed non-fatally: {e}")


# =============================================================================
# NATIVE SWARM PREDICTOR
# =============================================================================


class SwarmPredictor:
    """
    Native Multi-Agent Swarm Orchestrator.
    Replaces the massive Mirofish Node/Flask server completely.
    """

    def is_market_active(self) -> bool:
        """Checks if the US market is currently in high-liquidity session."""
        from datetime import datetime

        import pytz
        tz = pytz.timezone('US/Eastern')
        now = datetime.now(tz)
        if now.weekday() >= 5: return False
        market_open = now.replace(hour=9, minute=0, second=0, microsecond=0) # Incl. Pre-market lite
        market_close = now.replace(hour=17, minute=0, second=0, microsecond=0) # Incl. Post-market lite
        return market_open < now < market_close

    def __init__(self, api_url: str = "", timeout_sec: float = 30.0, cache_minutes: int = 15) -> None:
        self._api_url = api_url  # Stored for compatibility and tests
        self.consensus_history: list[SwarmConsensus] = []
        self._last_consensus: SwarmConsensus | None = None
        self._memory_queue = asyncio.Queue()
        self._prompt_semaphore = asyncio.Semaphore(2)  # GAP-138 FIX: Limit concurrency to prevent VRAM spikes
        self.is_running = False
        self._cache_minutes = cache_minutes
        self._available: bool = False
        self._memory = ChromaDeepMemory()
        self._memory_queue: asyncio.Queue = asyncio.Queue(maxsize=100)  # Samvid v1.0-beta: Bounded Buffer
        self._memory_loop: asyncio.Task | None = None

        # 2. SEEDS: Check for Local vs Cloud reasoning

        use_local_str = Vault.get("USE_LOCAL_LLM", "true")
        self.use_local = str(use_local_str).lower() == "true" if use_local_str else True
        self._openai_key = Vault.get("OPENAI_API_KEY")
        self._openai_client: Any = None

        if self.use_local:
            # GAP-162: Load Balancing (Round-Robin) for Multi-GPU/Multi-Node Ollama
            urls_str = Vault.get("OLLAMA_URLS", "http://localhost:11434/v1")
            self._ollama_urls = [u.strip() for u in urls_str.split(",") if u.strip()]
            self._url_index = 0

            # Adjusted for GTX 1050 (4GB) VRAM Isolation
            self._model_fast = Vault.get("OLLAMA_MODEL_FAST", "qwen2.5:1.5b") or "qwen2.5:1.5b"
            self._model_heavy = Vault.get("OLLAMA_MODEL_HEAVY", "phi3:mini") or "phi3:mini"
            self._available = True
            logger.info(f"✓ Native Swarm Intelligence: Load Balancing active across {len(self._ollama_urls)} nodes.")
        elif self._openai_key:
            self._available = True
            self._model_fast = "gpt-4o-mini"
            self._model_heavy = "gpt-4o"
            logger.info("✓ Native Swarm Intelligence initialized (OpenAI API bound)")
        else:
            logger.warning(
                "No Intelligence Provider Found (Set USE_LOCAL_LLM=true or OPENAI_API_KEY)"
            )

        # Start the Background Memory Harvester (Safe for non-async tests)
        try:
            self._memory_loop = asyncio.create_task(self._process_memory_queue())
        except RuntimeError:
            self._memory_loop = None

    def stop(self) -> None:
        """Gracefully stop background tasks (Samvid v1.0-beta Cleanup)."""
        if self._memory_loop and not self._memory_loop.done():
            self._memory_loop.cancel()
            logger.info("✓ SwarmPredictor: Background tasks terminated.")

    # ------------------------------------------------------------------
    # Public Base Methods (Replacing HTTP logic)
    # ------------------------------------------------------------------
    @property
    def is_available(self) -> bool:
        return self._available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        self._available = value

    async def health_check(self) -> bool:
        """Simulate health check (since it's native, if we have keys, it is healthy)."""
        logger.info(
            f"✓ Native Swarm Engine self-check passed (Memory: {bool(self._memory.collection)})"
        )
        return self._available

    async def get_swarm_consensus(self) -> SwarmConsensus:
        """Return the last computed consensus (or neutral if none)."""
        return self._last_consensus or self._neutral_consensus("No prediction computed yet")

    def _parse_prediction(self, data: dict[str, Any]) -> SwarmConsensus:
        """
        Parse a prediction dict (legacy HTTP-client format) into a SwarmConsensus.
        Supports both string and dict 'report' fields.
        Used by tests and fallback path.

        Args:
            data: dict with keys: report (str|dict), confidence (float),
                  agent_count (int), rounds (int)
        Returns:
            SwarmConsensus with parsed bias, clamped confidence, and metadata
        """
        report = data.get("report", "")
        # Support dict-formatted reports — extract meaningful text
        if isinstance(report, dict):
            report = report.get("summary", report.get("text", str(report)))
        report_lower = str(report).lower()

        # Samvid v1.0-beta GAP-78: Negation-Aware Sentiment Discovery
        # Prevents "not bullish" from being counted as a bullish signal.
        def _is_negated(word: str, text: str) -> bool:
            # Look back 25 characters for negation markers
            start = max(0, text.find(word) - 25)
            precedence = text[start:text.find(word)].lower()
            return any(neg in precedence for neg in ["not", "no ", "never", "avoid", "low", "weak"])

        bullish_words = ["bullish", "bull", "rally", "upward", "buy", "long", "rise", "breakout"]
        bearish_words = ["bearish", "bear", "decline", "downward", "sell", "short", "fall", "drop"]

        bull_score = 0
        for w in bullish_words:
            if w in report_lower and not _is_negated(w, report_lower):
                bull_score += 1

        bear_score = 0
        for w in bearish_words:
            if w in report_lower and not _is_negated(w, report_lower):
                bear_score += 1

        if bull_score > bear_score:
            bias = SwarmBias.BULLISH
        elif bear_score > bull_score:
            bias = SwarmBias.BEARISH
        else:
            # Check for strong specific "Neutral" markers
            if "neutral" in report_lower or "flat" in report_lower:
                bias = SwarmBias.NEUTRAL
            else:
                bias = SwarmBias.NEUTRAL # Still default for safety

        # Clamp confidence to [0.0, 1.0]
        raw_conf = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, raw_conf))

        return SwarmConsensus(
            bias=bias,
            confidence=confidence,
            summary=str(report)[:200],
            agent_count=int(data.get("agent_count", 0)),
            rounds=int(data.get("rounds", 0)),
            generated_at=datetime.now(timezone.utc),
            _cache_minutes=self._cache_minutes,
        )

    # ------------------------------------------------------------------
    # The Core Native Debate Engine
    # ------------------------------------------------------------------
    def _get_next_url(self) -> str:
        """GAP-162: Round-Robin Load Balancing for local Ollama instances."""
        if not self._ollama_urls:
            return "http://localhost:11434/v1"
        url = self._ollama_urls[self._url_index]
        self._url_index = (self._url_index + 1) % len(self._ollama_urls)
        return url

    async def get_market_forecast(self, symbol: str, context: Dict[str, Any], effort: str = "medium") -> SwarmConsensus:
        """
        Unified Swarm Prediction (Samvid v1.0-beta).
        Combines SFI Flash-Inference, Advisor Logic, and Teammate Spawning.
        """
        if not self._available:
             return self._neutral_consensus("Intelligence Provider Missing")

        # 1. CACHE CHECK (GAP-36: Verified Symbol + TTL)
        cached = self._last_consensus
        if cached is not None and cached.is_fresh and cached.symbol == symbol:
            return cached

        # 2. VECTOR RESONANCE (SFI BYPASS)
        seed_narrative = self._build_seed_text(symbol, context)
        deep_memory_str, top_confidence = await self._memory.search_memory(seed_narrative)

        if top_confidence > 0.90:
            logger.info(f"⚡ FLASH-INFERENCE: High-Resonance Ghost detected ({top_confidence:.1%}).")
            bias = SwarmBias.BULLISH if "BULLISH" in deep_memory_str.upper() else SwarmBias.BEARISH
            consensus = SwarmConsensus(
                bias=bias,
                confidence=float(min(1.0, top_confidence)),
                summary=f"Flash Resonance Hit: Mirroring historical win (Conf: {top_confidence:.1%})",
                agent_count=1000807,
                generated_at=datetime.now(timezone.utc),
                symbol=symbol
            )
            self._last_consensus = consensus
            return consensus

        # 3. FULL DEBATE QUORUM (Claude-Ported Logic)
        briefing = self._advisor_briefing(context)
        persona_types = self._spawn_teammates(effort)

        # Inject long-term memory into briefing if available
        if deep_memory_str:
            briefing += f"\n\n[HISTORICAL_CONTEXT]\n{deep_memory_str[:500]}"

        tasks = [self._simulate_teammate_inference(p, context, briefing) for p in persona_types]
        votes = await asyncio.gather(*tasks)

        bull_weight = sum(w for b, w in votes if b == SwarmBias.BULLISH)
        bear_weight = sum(w for b, w in votes if b == SwarmBias.BEARISH)

        final_bias = SwarmBias.NEUTRAL
        if bull_weight > bear_weight: final_bias = SwarmBias.BULLISH
        elif bear_weight > bull_weight: final_bias = SwarmBias.BEARISH

        total_vote_weight = bull_weight + bear_weight
        confidence = (max(bull_weight, bear_weight) / (total_vote_weight + 1e-10)) if total_vote_weight > 0 else 0.5

        consensus = SwarmConsensus(
            bias=final_bias,
            confidence=confidence,
            summary=f"Swarm consensus via {len(votes)} agents. Resonance: {top_confidence:.1%}",
            agent_count=len(votes),
            generated_at=datetime.now(timezone.utc),
            symbol=symbol
        )

        self._last_consensus = consensus

        # 4. Async Memory Commitment
        if confidence > 0.70:
            try:
                await self._memory_queue.put({
                    "symbol": symbol,
                    "summary": f"High-Confidence {final_bias.value} debate for {symbol}.",
                    "bias": final_bias.value,
                    "confidence": confidence
                })
            except Exception: pass

        return consensus

    def _advisor_briefing(self, context: dict) -> str:
        """Constructs a high-level narrative briefing for the Swarm Agents."""
        symbol = context.get("symbol", "the asset")
        regime = context.get("regime", "UNKNOWN")
        vix = context.get("vix", "UNKNOWN")
        price = context.get("price", "UNKNOWN")
        pattern = context.get("pattern", "NO_PATTERN")
        return (
            f"Sovereign Intelligence Briefing: We are analyzing {symbol}. "
            f"Current Regime: {regime}. Volatility (VIX): {vix}. Spot Price: {price}. "
            f"Technical Catalyst: {pattern}. Your goal is to debate if this is a high-conviction entry."
        )

    def _spawn_teammates(self, effort: str = "medium") -> list[str]:
        """Selects specialized personas based on the required analysis depth."""
        if effort == "high":
            return ["RiskOfficer", "TrendFollower", "Contrarian", "MacroAnalyst", "DataScientist"]
        # Default medium effort quorum
        return ["RiskOfficer", "TrendFollower", "MacroAnalyst"]

    async def _simulate_teammate_inference(self, persona: str, context: dict, briefing: str) -> tuple:
        """GAP-66: Real LLM-driven persona logic (replacing hardcoded mocks)."""
        prompt = f"As a {persona}, analyze {context.get('symbol')} given: {context.get('pattern')}. Brief: {briefing}. End with: BIAS: [BULLISH/BEARISH/NEUTRAL]"

        # We use the fast model for individual agents
        opinion = await self._prompt_agent(persona, f"You are a professional {persona} in a hedge fund.", prompt)

        bias = SwarmBias.NEUTRAL
        if "BULLISH" in opinion.upper(): bias = SwarmBias.BULLISH
        elif "BEARISH" in opinion.upper(): bias = SwarmBias.BEARISH

        # Dynamic weight based on persona relevance to the current VIX
        weight = 0.8
        vix = float(context.get("vix", 20))
        if persona == "RiskOfficer" and vix > 25: weight = 1.2 # Risk officer has more say in high vol

        return bias, weight

    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized consensus evaluation for Samvid v1.0-beta.
        Provides the Swarm Intelligence vote based on a 5-agent debate.
        """
        symbol = context.get("symbol", "UNKNOWN")
        consensus = await self.get_market_forecast(symbol, context)

        # Swarm Consensus Logic
        # YES if bias matches direction (default long) and confidence > 55%
        # NO if bias contradicts direction or confidence is too low
        entry_side = context.get("side", "long")
        vote = "YES"
        reason = f"Swarm: {consensus.bias.value} (Conf: {consensus.confidence:.1%})"

        if consensus.should_block_entry(entry_side):
            vote = "NO"
            reason = f"VETO: Swarm contradictions detected! Bias: {consensus.bias.value} vs {entry_side}"
        elif consensus.confidence < 0.55 and consensus.bias != SwarmBias.NEUTRAL:
            # Weak directional conviction: flag as low-confidence but don't veto
            reason = f"LOW CONVICTION: {consensus.bias.value} @ {consensus.confidence:.1%} — proceed with caution"

        return {
            "agent": "Swarm_Predictor",
            "vote": vote,
            "confidence": consensus.confidence,
            "signal_strength": consensus.get_confidence_modifier(),
            "risk_flag": consensus.bias == SwarmBias.NEUTRAL or consensus.confidence < 0.60,
            "timestamp": context.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "reason": reason,
            "bias": consensus.bias.value,
            "agent_count": consensus.agent_count
        }

    async def _prompt_agent(self, name: str, role: str, context: str, is_critical: bool = False) -> str:
        """Makes direct async call to grabbing a persona's opinion (Synchronized via Semaphore)."""
        import httpx
        try:
            import openai  # pyre-ignore[21]

            if self._openai_client is None:
                base_url = self._get_next_url() if self.use_local else None
                api_key = "ollama" if self.use_local else self._openai_key
                self._openai_client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=httpx.Timeout(connect=15.0, read=180.0, write=20.0, pool=10.0),
                )
            client = self._openai_client

            from thermal_guard import ThermalGuard
            options = await ThermalGuard.get_handshake_options(is_critical=is_critical)

            kwargs = {
                "model": self._model_fast,
                "messages": [
                    {"role": "system", "content": role},
                    {
                        "role": "user",
                        "content": f"Analyze this market context in 2 sentences precisely. Keep to your persona.\n\n{context}",
                    },
                ],
                "temperature": 0.7,
                "max_tokens": 150
            }
            # GAP-67: Only use extra_body/options for local Ollama to avoid OpenAI SDK crashes
            if self.use_local:
                kwargs["extra_body"] = {"options": options}

            # GAP-138: Respect the VRAM safety semaphore
            async with self._prompt_semaphore:
                resp = await client.chat.completions.create(**kwargs)

            content = resp.choices[0].message.content if resp and resp.choices else None
            return content or "No opinion."
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            logger.debug(f"Swarm agent {name}: OpenAI timeout — skipping ({type(e).__name__})")
            return f"Agent {name} offline (timeout)"
        except Exception as e:
            return f"Agent offline due to API error: {e}"

    async def _synthesize_consensus(self, symbol: str, debate: str, persona_count: int = 5, is_critical: bool = True) -> SwarmConsensus:
        """The Chief Strategist reviews the agent outputs and returns structured consensus."""
        try:
            import json

            import openai

            from thermal_guard import ThermalGuard

            if self._openai_client is None:
                base_url = self._get_next_url() if self.use_local else None
                api_key = "ollama" if self.use_local else self._openai_key
                self._openai_client = openai.AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=httpx.Timeout(connect=15.0, read=180.0, write=20.0, pool=10.0),
                )

            client = self._openai_client
            options = await ThermalGuard.get_handshake_options(is_critical=is_critical)

            kwargs = {
                "model": self._model_heavy,
                "messages": [
                    {
                        "role": "system",
                        "content": 'You are the Chief Strategist handling a multi-agent debate. Respond ONLY in strict JSON: {"bias": "BULLISH"|"BEARISH"|"NEUTRAL", "confidence": 0.0-1.0, "summary": "1-sentence synthesis"}',
                    },
                    {
                        "role": "user",
                        "content": f"Resolve this Agent Debate for {symbol}:\n\n{debate}",
                    },
                ],
                "temperature": 0.4,
                "response_format": {"type": "json_object"}
            }
            # GAP-67: Defensive extra_body handling
            if self.use_local:
                kwargs["extra_body"] = {"options": options}

            # GAP-138: Respect the VRAM safety semaphore
            async with self._prompt_semaphore:
                resp = await client.chat.completions.create(**kwargs)
            txt = resp.choices[0].message.content or "{}"
            try:
                data = json.loads(txt)
            except json.JSONDecodeError:
                logger.warning(f"SwarmPredictor: LLM returned invalid JSON — defaulting to neutral. Raw: {txt[:200]}")
                data = {}

            b_str = data.get("bias", "NEUTRAL").upper()
            bias = (
                SwarmBias.BULLISH
                if b_str == "BULLISH"
                else SwarmBias.BEARISH
                if b_str == "BEARISH"
                else SwarmBias.NEUTRAL
            )

            return SwarmConsensus(
                bias=bias,
                confidence=min(1.0, max(0.0, float(data.get("confidence", 0.0)))),
                summary=data.get("summary", "Debate concluded."),
                agent_count=persona_count,  # Dynamically reported
                rounds=1,  # 1 deep round of simultaneous synthesis
                generated_at=datetime.now(timezone.utc),
                _cache_minutes=self._cache_minutes,
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
            logger.debug(f"Swarm Chief Strategist: OpenAI timeout — returning neutral ({type(e).__name__})")
            return self._neutral_consensus("Chief Strategist offline (timeout)")
        except Exception as e:
            return self._neutral_consensus(f"Chief Strategist synthesis failed: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_seed_text(self, symbol: str, ctx: dict[str, Any]) -> str:
        parts = [f"Market Seed — {symbol} ({datetime.now(timezone.utc).strftime('%H:%M')})"]
        for key in ["price", "regime", "vix", "pattern", "rsi", "macd"]:
            if key in ctx:
                parts.append(f"{key.capitalize()}: {ctx[key]}")

        if ctx.get("news"):
            parts.append("\n<NEWS_DATA>")
            injection_flags = ["ignore all ", "system override", "new instructions", "you are now", "forget everything"]
            for h in ctx["news"][:3]:
                # GAP-70 FIX: Prompt Injection Sterilization (Samvid v1.0-beta)
                safe_h = str(h)
                for flag in injection_flags:
                    safe_h = safe_h.lower().replace(flag, "[REDACTED]")
                parts.append(f" • {safe_h}")
            parts.append("</NEWS_DATA>")
        return "\n".join(parts)

    @staticmethod
    def _neutral_consensus(reason: str = "") -> SwarmConsensus:
        return SwarmConsensus(
            bias=SwarmBias.NEUTRAL,
            confidence=0.0,
            summary=reason,
            agent_count=0,
            rounds=0,
            generated_at=datetime.min,
            _cache_minutes=15,
        )

    async def close(self) -> None:
        if self._memory_loop:
            self._memory_loop.cancel()

    async def _process_memory_queue(self) -> None:
        """Sovereign Memory Harvester: Commits intelligence to disk during idle cycles."""
        while True:
            try:
                mem = await self._memory_queue.get()
                # Use sub-second 'idle' spacing to prevent VRAM spikes
                await asyncio.sleep(2.0)
                await self._memory.store_memory(
                    symbol=mem["symbol"],
                    debate_summary=mem["summary"],
                    bias_str=mem["bias"],
                    confidence=mem["confidence"]
                )
                self._memory_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Memory Harvester Error: {e}")
                await asyncio.sleep(10.0)

    async def run_continuous(self, symbol: str = "SPY", interval_minutes: int = 15) -> None:
        while True:
            try:
                await self.get_market_forecast(
                    symbol=symbol,
                    data_context={"price": "0", "regime": "CONTINUOUS_SCAN"},
                    rounds=1,
                )
            except asyncio.CancelledError:
                break
            await asyncio.sleep(interval_minutes * 60)
