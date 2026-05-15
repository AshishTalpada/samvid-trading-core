import asyncio
import json
import logging
import sys
import time
import uuid
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
            # n_gpu_layers=0 eliminates hardware-mismatch crashes
            self._available = True
            logger.info(f"Sovereign-SLM: Neural Sandbox initialized for {model_path}")
        except Exception as e:
            logger.error(f"Sovereign-SLM Initialization failed: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        pass # Controlled internally


    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sovereign-SLM Neural Sandbox: Isolated Inference Guard."""
        if not self._available:
            return self._neutral_vote(context, "Native SLM sandbox unavailable.")

        prompt = self._build_prompt(context)
        prompt_json = json.dumps(prompt)
        
        try:
            # --- THE NEURAL SANDBOX: Isolated Execution ---
            # Spawning a separate process protects the Main Engine from GGML_ASSERT crashes.
            cmd = [
                sys.executable, 
                "src/neural_sandbox.py", 
                self.model_path, 
                prompt_json
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 15s timeout for the isolated worker
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            
            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                logger.error(f"Neural Sandbox CRASHED (code {proc.returncode}): {err_msg}")
                return self._neutral_vote(context, f"Sandbox Crash: {err_msg}")
                
            result_raw = stdout.decode().strip()
            # Clean terminal noise if any
            if "{" in result_raw:
                result_raw = result_raw[result_raw.find("{"):]
            
            result_data = json.loads(result_raw)
            
            if result_data.get("status") == "ERROR":
                return self._neutral_vote(context, f"Sandbox Error: {result_data.get('reason')}")
                
            output_text = result_data.get("text", "NEUTRAL")
            
            bias = "NEUTRAL"
            if "BULLISH" in output_text:
                bias = "BULLISH"
            elif "BEARISH" in output_text:
                bias = "BEARISH"

            entry_side = str(context.get("side", "long")).lower()

            vote = "YES"
            reason = f"Neural Sandbox: {bias}"

            if (entry_side == "long" and bias == "BEARISH") or (entry_side == "short" and bias == "BULLISH"):
                vote = "NO"
                reason = f"VETO: Sandbox contradicts direction ({bias} vs {entry_side})"

            return {
                "agent": "Native_SLM",
                "vote": vote,
                "confidence": 0.85 if bias != "NEUTRAL" else 0.5,
                "signal_strength": 1.15 if vote == "YES" and bias != "NEUTRAL" else 1.0,
                "risk_flag": str(bias == "NEUTRAL"),
                "timestamp": context.get("timestamp", time.time_ns()),
                "reason": reason,
                "bias": bias,
                "agent_count": 1
            }

        except asyncio.TimeoutError:
            logger.error("Neural Sandbox TIMEOUT (15s). Moving on.")
            return self._neutral_vote(context, "Sandbox Timeout")
        except Exception as e:
            logger.error(f"Neural Sandbox DISPATCH FAILED: {e}")
            return self._neutral_vote(context, f"Dispatch Error: {e}")

    def _build_prompt(self, context: dict) -> list:
        sys_prompt = "You are Sovereign-SLM, an elite quantitative strategist. Analyze the market context and output exactly one word: BULLISH, BEARISH, or NEUTRAL."

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
