import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)


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

            # If the model doesn't exist, give it its 'first breath' by downloading a high-speed base model
            if not os.path.exists(model_path):
                logger.info(
                    f"Model not found at {model_path}. Awakening the SLM by downloading Qwen2.5-0.5B base model..."
                )
                try:
                    from huggingface_hub import hf_hub_download

                    os.makedirs(os.path.dirname(model_path), exist_ok=True)
                    downloaded_path = hf_hub_download(
                        repo_id="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
                        filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
                        local_dir=os.path.dirname(model_path),
                    )
                    # Rename the downloaded file to match our expected path
                    if os.path.exists(downloaded_path) and downloaded_path != model_path:
                        import shutil

                        shutil.move(downloaded_path, model_path)
                    logger.info("✅ First Breath successful. Base model downloaded.")
                except Exception as dl_err:
                    logger.error(f"Failed to download base model: {dl_err}")
                    return

            logger.info(f"Loading Native SLM into memory from {model_path}...")
            # n_gpu_layers=-1 attempts to offload entirely to GPU if compiled with cuBLAS/Metal
            self.model = Llama(model_path=model_path, n_gpu_layers=-1, n_ctx=2048, verbose=False)
            self._available = True
            logger.info("✅ Native SLM successfully loaded into VRAM.")
        except Exception as e:
            logger.error(f"Failed to load Native SLM: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        pass  # Controlled internally

    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Drop-in replacement for SwarmPredictor's evaluate_proposal."""
        if not self._available or not self.model:
            return self._neutral_vote(context, "Native SLM offline or unavailable.")

        prompt = self._build_prompt(context)

        try:
            # Run inference in a thread pool so it doesn't block the async HFT event loop
            response = await asyncio.to_thread(
                self.model.create_chat_completion,
                messages=prompt,
                max_tokens=10,
                temperature=0.1,  # Very deterministic for trading
            )

            output_text = response["choices"][0]["message"]["content"].strip().upper()

            bias = "NEUTRAL"
            if "BULLISH" in output_text:
                bias = "BULLISH"
            elif "BEARISH" in output_text:
                bias = "BEARISH"

            entry_side = context.get("side", "long").lower()

            vote = "YES"
            reason = f"Native SLM: {bias}"

            # Simple contradiction check
            if (entry_side == "long" and bias == "BEARISH") or (
                entry_side == "short" and bias == "BULLISH"
            ):
                vote = "NO"
                reason = f"VETO: SLM contradicts direction ({bias} vs {entry_side})"

            return {
                "agent": "Native_SLM",
                "vote": vote,
                "confidence": 0.85
                if bias != "NEUTRAL"
                else 0.5,  # Static conf since SLM is decisive
                "signal_strength": 1.15 if vote == "YES" and bias != "NEUTRAL" else 1.0,
                "risk_flag": bias == "NEUTRAL",
                "timestamp": context.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "reason": reason,
                "bias": bias,
                "agent_count": 1,  # It's a single brain, not a swarm
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
            {"role": "user", "content": f"Context:\n{ctx_str}"},
        ]

    def _neutral_vote(self, context: dict, reason: str) -> dict:
        return {
            "agent": "Native_SLM",
            "vote": "YES",  # Default pass if SLM is offline
            "confidence": 0.0,
            "signal_strength": 1.0,
            "risk_flag": True,
            "timestamp": context.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "reason": reason,
            "bias": "NEUTRAL",
            "agent_count": 0,
        }

    async def close(self) -> None:
        if self.model:
            # Free VRAM
            del self.model
            self.model = None
            self._available = False
            logger.info("Native SLM unloaded from VRAM.")


if __name__ == "__main__":
    # Test script to give her 'first breath'
    import asyncio

    async def main():
        logging.basicConfig(level=logging.INFO)
        slm = NativeSLM()
        if slm.is_available:
            print("\n--- Testing Native SLM Inference ---")
            dummy_context = {
                "symbol": "EURUSD",
                "regime": "Trending",
                "dhatu_state": "Vriddhi",
                "pattern": "Breakout",
                "catalyst_score": 0.85,
                "belief": 0.9,
                "side": "long",
            }
            result = await slm.evaluate_proposal(dummy_context)
            print(f"Result: {result}")
            await slm.close()
        else:
            print("Native SLM failed to initialize.")

    asyncio.run(main())
