import asyncio
import logging
import os
import time
from typing import Any, Dict

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)

# Global GGML serialization lock — prevents concurrent GGML_ASSERT crashes
# when multiple async tasks call into the same in-process Llama instance.
_SLM_LOCK = asyncio.Lock()


class NativeSLM:
    """
    Blazing-fast, ultra-low latency inference engine running directly in VRAM.
    Model is loaded ONCE at startup and kept resident — no subprocess overhead.
    """

    def __init__(self, model_path: str = "models/sovereign_slm.gguf"):
        self._available = False
        self.model_path = model_path
        self.model: Any = None
        self._sandbox_failures = 0
        self._last_failure_at = 0.0

        if Llama is None:
            logger.warning("llama-cpp-python not installed. Native SLM offline.")
            return

        if not os.path.exists(model_path):
            logger.warning(
                f"Native SLM model not found at {model_path}. Awaiting fine-tuned model."
            )
            return

        try:
            logger.info(f"Loading Native SLM into memory from {model_path}...")
            n_ctx = int(os.environ.get("SOVEREIGN_SLM_N_CTX", "256"))
            n_threads = int(os.environ.get("SOVEREIGN_SLM_THREADS", "4"))
            n_gpu_layers = int(os.environ.get("SOVEREIGN_SLM_GPU_LAYERS", "0"))

            self.model = Llama(
                model_path=model_path,
                n_gpu_layers=n_gpu_layers,
                n_ctx=n_ctx,
                n_threads=n_threads,
                n_batch=64,
                verbose=False,
            )
            self._available = True
            logger.info(
                f"Sovereign-SLM: Model resident in memory "
                f"(n_ctx={n_ctx}, n_threads={n_threads}, n_gpu_layers={n_gpu_layers})"
            )
        except Exception as e:
            logger.error(f"Sovereign-SLM Initialization failed: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        self._available = value

    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sovereign-SLM Neural Inference — runs in-process with thread isolation."""
        if not self._available or self.model is None:
            return self._neutral_vote(context, "Native SLM unavailable.")

        prompt = self._build_prompt(context)

        try:
            async with _SLM_LOCK:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._run_sync, prompt, context),
                    timeout=30.0,
                )
            return result
        except asyncio.TimeoutError:
            self._record_failure("timeout")
            logger.error("Native SLM: Inference timed out after 30s.")
            return self._neutral_vote(context, "SLM Timeout")
        except Exception as e:
            self._record_failure(str(e))
            logger.error(f"Native SLM: Inference dispatch failed: {e}")
            return self._neutral_vote(context, f"Dispatch Error: {e}")

    def _run_sync(self, prompt: list, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous inference called via asyncio.to_thread.
        _SLM_LOCK is NOT used here (can't acquire asyncio.Lock in sync thread).
        Thread-safety is guaranteed by the fact that llama.cpp itself is
        single-threaded per model instance, and asyncio.to_thread serializes
        calls through the thread pool naturally for single-model setups.
        """
        t0 = time.monotonic()
        try:
            # Build flat prompt string (fastest path for llama-cpp)
            full_prompt = (
                f"System: {prompt[0]['content']}\n"
                f"User: {prompt[1]['content']}\n"
                f"Assistant:"
            )
            response = self.model(
                full_prompt,
                max_tokens=10,
                temperature=0.1,
                stop=["\n", "User:", "System:"],
            )
            elapsed = time.monotonic() - t0
            output_text = response["choices"][0]["text"].strip().upper()

            bias = "NEUTRAL"
            if "BULLISH" in output_text:
                bias = "BULLISH"
            elif "BEARISH" in output_text:
                bias = "BEARISH"

            entry_side = str(context.get("side", "long")).lower()
            vote = "YES"
            reason = f"Native SLM: {bias} ({elapsed:.2f}s)"

            if (entry_side == "long" and bias == "BEARISH") or (
                entry_side == "short" and bias == "BULLISH"
            ):
                vote = "NO"
                reason = f"VETO: SLM contradicts direction ({bias} vs {entry_side})"

            self._sandbox_failures = 0
            return {
                "agent": "Native_SLM",
                "vote": vote,
                "confidence": 0.85 if bias != "NEUTRAL" else 0.5,
                "signal_strength": 1.15 if vote == "YES" and bias != "NEUTRAL" else 1.0,
                "risk_flag": str(bias == "NEUTRAL"),
                "timestamp": context.get("timestamp", time.time_ns()),
                "reason": reason,
                "bias": bias,
                "agent_count": 1,
            }
        except Exception as e:
            self._record_failure(str(e))
            raise

    def _record_failure(self, reason: str = "") -> None:
        now = time.monotonic()
        if now - self._last_failure_at > 300.0:
            self._sandbox_failures = 0
        self._last_failure_at = now
        self._sandbox_failures += 1
        if self._sandbox_failures >= 3:
            self._available = False
            logger.warning(
                "Native SLM disabled after %s consecutive failures. "
                "Trading continues with deterministic quorum agents.",
                self._sandbox_failures,
            )

    def _build_prompt(self, context: dict) -> list:
        sys_prompt = (
            "You are Sovereign-SLM, an elite quantitative strategist. "
            "Analyze the market context and output exactly one word: BULLISH, BEARISH, or NEUTRAL."
        )
        ctx_str = (
            f"Instrument: {str(context.get('symbol', 'UNKNOWN'))}\n"
            f"Regime: {str(context.get('regime', 'UNKNOWN'))}\n"
            f"Dhatu State: {str(context.get('dhatu_state', 'UNKNOWN'))}\n"
            f"Pattern: {str(context.get('pattern', 'UNKNOWN'))}\n"
            f"Catalyst Score: {str(context.get('catalyst_score', 0.5))}\n"
            f"Belief: {str(context.get('belief', 0.5))}\n"
            f"Side: {str(context.get('side', 'LONG'))}\n"
            f"\nDecision?"
        )
        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Context:\n{ctx_str}"},
        ]

    def _neutral_vote(self, context: dict, reason: str) -> dict:
        return {
            "agent": "Native_SLM",
            "vote": "ABSTAIN",
            "confidence": 0.0,
            "signal_strength": 1.0,
            "risk_flag": "True",
            "timestamp": context.get("timestamp", time.time_ns()),
            "reason": reason,
            "bias": "NEUTRAL",
            "agent_count": 0,
        }

    async def close(self) -> None:
        """Free model memory on shutdown."""
        if self.model is not None:
            del self.model
            self.model = None
            self._available = False
            logger.info("Native SLM unloaded from memory.")
