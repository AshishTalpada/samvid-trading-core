import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

logger = logging.getLogger(__name__)

_SLM_LOCK = asyncio.Lock()


class NativeSLM:
    """
    Crash-isolated native inference facade.

    llama.cpp GGML asserts are process-fatal. Keeping the model in the trading
    process is fast, but unsafe. This facade keeps a resident child worker alive
    for speed while preserving a hard process boundary around native code.
    """

    def __init__(self, model_path: str = "models/sovereign_slm.gguf"):
        self._available = False
        self.model_path = model_path
        self._worker: asyncio.subprocess.Process | None = None
        self._sandbox_failures = 0
        self._last_failure_at = 0.0
        self._last_restart_at = 0.0
        self._startup_timeout = float(os.environ.get("SOVEREIGN_SLM_STARTUP_TIMEOUT", "45"))
        self._inference_timeout = float(os.environ.get("SOVEREIGN_SLM_TIMEOUT", "8"))

        if Llama is None:
            logger.warning("llama-cpp-python not installed. Native SLM offline.")
            return

        if not os.path.exists(model_path):
            logger.warning(
                "Native SLM model not found at %s. Awaiting fine-tuned model.",
                model_path,
            )
            return

        self._available = True
        logger.info(
            "Sovereign-SLM: crash-isolated resident worker armed for %s.",
            model_path,
        )

    @property
    def is_available(self) -> bool:
        return self._available

    @is_available.setter
    def is_available(self, value: bool) -> None:
        self._available = value

    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a trade proposal through the isolated resident SLM worker."""
        if not self._available:
            return self._neutral_vote(context, "Native SLM unavailable.")

        prompt = self._build_prompt(context)
        request_id = uuid.uuid4().hex

        try:
            async with _SLM_LOCK:
                worker = await self._ensure_worker()
                if worker is None or worker.stdin is None or worker.stdout is None:
                    return self._neutral_vote(context, "Native SLM worker unavailable.")

                payload = {
                    "id": request_id,
                    "prompt": prompt,
                    "max_tokens": 3,
                    "temperature": 0.1,
                }
                wire = json.dumps(payload, separators=(",", ":")) + "\n"
                started = time.monotonic()
                worker.stdin.write(wire.encode("utf-8"))
                await worker.stdin.drain()

                raw = await asyncio.wait_for(
                    worker.stdout.readline(),
                    timeout=self._inference_timeout,
                )
                if not raw:
                    raise RuntimeError("worker exited without response")

                elapsed = time.monotonic() - started
                data = json.loads(raw.decode("utf-8", errors="replace"))
                if data.get("id") != request_id:
                    raise RuntimeError("worker response id mismatch")
                if data.get("status") != "SUCCESS":
                    raise RuntimeError(str(data.get("reason", "unknown worker error")))

            self._sandbox_failures = 0
            return self._vote_from_text(str(data.get("text", "")), context, elapsed)
        except asyncio.TimeoutError:
            await self._kill_worker("timeout")
            self._record_failure("timeout")
            logger.error("Native SLM: worker timed out after %.1fs.", self._inference_timeout)
            return self._neutral_vote(context, "SLM Timeout")
        except Exception as exc:
            await self._kill_worker(str(exc))
            self._record_failure(str(exc))
            logger.error("Native SLM: isolated worker failed: %s", exc)
            return self._neutral_vote(context, f"Worker Error: {exc}")

    async def _ensure_worker(self) -> asyncio.subprocess.Process | None:
        if self._worker and self._worker.returncode is None:
            return self._worker

        now = time.monotonic()
        if now - self._last_restart_at < 2.0:
            await asyncio.sleep(2.0 - (now - self._last_restart_at))
        self._last_restart_at = time.monotonic()

        cmd = [sys.executable, "src/neural_sandbox.py", "--worker", self.model_path]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            if proc.stdout is None:
                raise RuntimeError("worker stdout unavailable")
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=self._startup_timeout)
            if not raw:
                raise RuntimeError("worker exited during startup")
            ready = json.loads(raw.decode("utf-8", errors="replace"))
            if ready.get("status") != "READY":
                raise RuntimeError(str(ready.get("reason", "worker startup failed")))
            self._worker = proc
            logger.info(
                "Native SLM worker ready (pid=%s, n_ctx=%s, n_batch=%s).",
                proc.pid,
                ready.get("n_ctx"),
                ready.get("n_batch"),
            )
            return proc
        except Exception:
            if "proc" in locals() and proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise

    async def _kill_worker(self, reason: str) -> None:
        proc = self._worker
        self._worker = None
        if proc is None or proc.returncode is not None:
            return
        logger.warning("Native SLM: killing worker pid=%s (%s).", proc.pid, reason)
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Native SLM: worker pid=%s did not exit after kill.", proc.pid)

    def _vote_from_text(self, output_text: str, context: Dict[str, Any], elapsed: float) -> dict:
        text = output_text.strip().upper()
        bias = "NEUTRAL"
        if "BULLISH" in text:
            bias = "BULLISH"
        elif "BEARISH" in text:
            bias = "BEARISH"

        entry_side = str(context.get("side", "long")).lower()
        vote = "YES"
        reason = f"Native SLM: {bias} ({elapsed:.2f}s)"
        if (entry_side == "long" and bias == "BEARISH") or (
            entry_side == "short" and bias == "BULLISH"
        ):
            vote = "NO"
            reason = f"VETO: SLM contradicts direction ({bias} vs {entry_side})"

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

    def _record_failure(self, reason: str = "") -> None:
        now = time.monotonic()
        if now - self._last_failure_at > 300.0:
            self._sandbox_failures = 0
        self._last_failure_at = now
        self._sandbox_failures += 1
        hard_native_failure = "ggml_assert" in reason.lower() or "access violation" in reason.lower()
        if hard_native_failure or self._sandbox_failures >= 3:
            self._available = False
            logger.warning(
                "Native SLM disabled after %s failure(s). Trading continues with "
                "deterministic quorum agents.",
                self._sandbox_failures,
            )

    def _build_prompt(self, context: dict) -> list:
        sys_prompt = (
            "You are Sovereign-SLM, an elite quantitative strategist. "
            "Output exactly one word: BULLISH, BEARISH, or NEUTRAL."
        )
        ctx_str = (
            f"Instrument: {str(context.get('symbol', 'UNKNOWN'))}\n"
            f"Regime: {str(context.get('regime', 'UNKNOWN'))}\n"
            f"Dhatu State: {str(context.get('dhatu_state', 'UNKNOWN'))}\n"
            f"Pattern: {str(context.get('pattern', 'UNKNOWN'))}\n"
            f"Catalyst Score: {str(context.get('catalyst_score', 0.5))}\n"
            f"Belief: {str(context.get('belief', 0.5))}\n"
            f"Side: {str(context.get('side', 'LONG'))}\n"
            "Decision?"
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
        await self._kill_worker("shutdown")
        self._available = False
