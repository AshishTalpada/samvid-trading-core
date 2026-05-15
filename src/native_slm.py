import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)

# Global Neural Semaphore: Prevent 'GGML_ASSERT' crash by serializing AI calls
_SLM_LOCK = asyncio.Lock()

class NativeSLM:
    """
    Blazing-fast, ultra-low latency inference engine running directly in VRAM.
    Bypasses all HTTP/REST API overhead.
    """
    def __init__(self, model_path: str = "models/sovereign_slm.gguf"):
        self._available = False
        self.model = None

        if Llama is None:
            logger.warning("llama-cpp-python not installed. Native SLM offline.")
            return

        try:
            import os
            # Only try to load if the file actually exists to prevent crashes
            if not os.path.exists(model_path):
                logger.warning(f"Native SLM model not found at {model_path}. Awaiting fine-tuned model.")
                return

            logger.info(f"Loading Native SLM into memory from {model_path}...")
            # n_gpu_layers=-1 attempts to offload entirely to GPU if compiled with cuBLAS/Metal
            # Increased context window to 8192 to utilize more of the model's training capacity.
            # This provides better 'intelligence' for multi-factor market analysis.
            # Safe Mode: Full CPU execution to prevent GGML_ASSERT memory overflows.
            # n_gpu_layers=0 eliminates hardware-mismatch crashes on Windows.
            self.model = Llama(
                model_path=model_path,
                n_gpu_layers=0,
                n_ctx=1024,
                n_threads=4,
                verbose=False
            )
            self._available = True
            logger.info(" Native SLM successfully loaded into VRAM.")
        except Exception as e:
            logger.error(f"Failed to load Native SLM: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        pass # Controlled internally


    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sovereign-SLM Sentiment Inference with Concurrency Guard."""
        if not self._available or not self.model:
            return self._neutral_vote(context, "Native SLM offline or unavailable.")

        async with _SLM_LOCK:
            prompt = self._build_prompt(context)
            try:
                # Use a more stable, explicit call for Windows/CPU execution.
                # We use a 0.05s safety buffer between inferences to prevent process-level locks.
                await asyncio.sleep(0.05)

                # Format prompt for basic completion to bypass chat-template overhead
                full_prompt = f"System: {prompt[0]['content']}\nUser: {prompt[1]['content']}\nAssistant:"

                response = await asyncio.to_thread(
                    self.model,
                    full_prompt,
                    max_tokens=15,
                    temperature=0.1,
                    stop=["\n", "User:", "System:"]
                )

                output_text = response["choices"][0]["text"].strip().upper()

                bias = "NEUTRAL"
                if "BULLISH" in output_text:
                    bias = "BULLISH"
                elif "BEARISH" in output_text:
                    bias = "BEARISH"

                entry_side = context.get("side", "long").lower()

                vote = "YES"
                reason = f"Native SLM: {bias}"

                # Simple contradiction check
                if (entry_side == "long" and bias == "BEARISH") or (entry_side == "short" and bias == "BULLISH"):
                    vote = "NO"
                    reason = f"VETO: SLM contradicts direction ({bias} vs {entry_side})"

                return {
                    "agent": "Native_SLM",
                    "vote": vote,
                    "confidence": 0.85 if bias != "NEUTRAL" else 0.5, # Static conf since SLM is decisive
                    "signal_strength": 1.15 if vote == "YES" and bias != "NEUTRAL" else 1.0,
                    "risk_flag": bias == "NEUTRAL",
                    "timestamp": context.get("timestamp", time.time_ns()),
                    "reason": reason,
                    "bias": bias,
                    "agent_count": 1 # It's a single brain, not a swarm
                }

            except Exception as e:
                logger.error(f"Native SLM Inference failed: {e}")
                return self._neutral_vote(context, f"Inference Error: {e}")

    def _build_prompt(self, context: dict) -> list:
        sys_prompt = "You are Sovereign-SLM, an elite quantitative strategist. Analyze the market context and output exactly one word: BULLISH, BEARISH, or NEUTRAL."

        ctx_str = (
            f"Instrument: {context.get('symbol', 'UNKNOWN')}\n"
            f"Regime: {context.get('regime', 'UNKNOWN')}\n"
            f"Dhatu State: {context.get('dhatu_state', 'UNKNOWN')}\n"
            f"Pattern: {context.get('pattern', 'UNKNOWN')}\n"
            f"Catalyst Score: {context.get('catalyst_score', 0.5)}\n"
            f"Belief: {context.get('belief', 0.5)}\n"
            f"\nDecision?"
        )

        return [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Context:\n{ctx_str}"}
        ]

    def _neutral_vote(self, context: dict, reason: str) -> dict:
        return {
            "agent": "Native_SLM",
            "vote": "YES", # Default pass if SLM is offline
            "confidence": 0.0,
            "signal_strength": 1.0,
            "risk_flag": True,
            "timestamp": context.get("timestamp", time.time_ns()),
            "reason": reason,
            "bias": "NEUTRAL",
            "agent_count": 0
        }

    async def close(self) -> None:
        if self.model:
            # Free VRAM
            del self.model
            self.model = None
            self._available = False
            logger.info("Native SLM unloaded from VRAM.")
