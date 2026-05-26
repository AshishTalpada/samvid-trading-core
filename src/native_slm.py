import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
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
        self._worker: asyncio.subprocess.Process | subprocess.Popen[bytes] | None = None
        self._sandbox_failures = 0
        self._last_failure_at = 0.0
        self._last_restart_at = 0.0
        self._fallback_mode = False
        self._compat_mode = False
        self._status_detail = "offline"
        self._startup_timeout = float(os.environ.get("SOVEREIGN_SLM_STARTUP_TIMEOUT", "45"))
        self._inference_timeout = float(os.environ.get("SOVEREIGN_SLM_TIMEOUT", "8"))
        self._quarantine_path = Path(
            os.environ.get("SOVEREIGN_SLM_QUARANTINE_FILE", "data/native_slm_quarantine.json")
        )

        if Llama is None:
            if os.path.exists(model_path):
                self._available = True
                self._fallback_mode = True
                self._status_detail = "deterministic fallback: llama-cpp-python missing"
                logger.warning(
                    "Native SLM runtime missing; deterministic fallback online for %s.",
                    model_path,
                )
            else:
                logger.info("llama-cpp-python not installed. Native SLM offline.")
            return

        if not os.path.exists(model_path):
            logger.warning(
                "Native SLM model not found at %s. Awaiting fine-tuned model.",
                model_path,
            )
            return

        quarantined_reason = self._load_quarantine_reason()
        if quarantined_reason and os.environ.get("SOVEREIGN_SLM_FORCE_NATIVE") != "1":
            self._available = True
            self._compat_mode = True
            self._status_detail = f"compat worker after native quarantine: {quarantined_reason}"
            logger.info("Native SLM native worker quarantined; %s.", self._status_detail)
            return

        self._available = True
        self._status_detail = "native isolated worker"
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

    @property
    def mode(self) -> str:
        if self._compat_mode:
            return "compat"
        return "fallback" if self._fallback_mode else ("native" if self._available else "offline")

    @property
    def status_detail(self) -> str:
        return self._status_detail

    async def evaluate_proposal(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a trade proposal through the isolated resident SLM worker."""
        if not self._available:
            return self._neutral_vote(context, "Native SLM unavailable.")
        if self._fallback_mode and not self._compat_mode:
            return self._fallback_vote(context, self._status_detail)

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
                    "context": context,
                    "max_tokens": 3,
                    "temperature": 0.1,
                }
                wire = json.dumps(payload, separators=(",", ":")) + "\n"
                started = time.monotonic()
                if isinstance(worker, subprocess.Popen):
                    await asyncio.to_thread(self._popen_write, worker, wire.encode("utf-8"))
                    raw = await asyncio.wait_for(
                        asyncio.to_thread(worker.stdout.readline),
                        timeout=self._inference_timeout,
                    )
                else:
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
            hard_failure = self._record_failure(str(exc))
            level = logging.WARNING if hard_failure else logging.ERROR
            logger.log(level, "Native SLM: isolated worker failed: %s", exc)
            if self._fallback_mode:
                return self._fallback_vote(context, self._status_detail)
            return self._neutral_vote(context, f"Worker Error: {exc}")

    async def warmup(self) -> bool:
        """Validate native worker startup once so status reporting is honest."""
        if not self._available or self._fallback_mode:
            return self._available
        try:
            worker = await self._ensure_worker()
            return worker is not None and self._worker_alive(worker)
        except Exception as exc:
            reason = str(exc) or exc.__class__.__name__
            await self._kill_worker(reason)
            self._record_failure(reason)
            if not self._fallback_mode and os.path.exists(self.model_path):
                self._fallback_mode = True
                self._available = True
                self._status_detail = f"deterministic fallback after warmup failure: {reason[:140]}"
            log = logger.info if self._fallback_mode else logger.warning
            log("Native SLM warmup completed in degraded mode; %s.", self._status_detail)
            return self._available

    async def _ensure_worker(
        self,
    ) -> asyncio.subprocess.Process | subprocess.Popen[bytes] | None:
        if self._worker and self._worker_alive(self._worker):
            return self._worker

        now = time.monotonic()
        if now - self._last_restart_at < 2.0:
            await asyncio.sleep(2.0 - (now - self._last_restart_at))
        self._last_restart_at = time.monotonic()

        cmd = (
            [sys.executable, "src/slm_compat_worker.py"]
            if self._compat_mode
            else [sys.executable, "src/neural_sandbox.py", "--worker", self.model_path]
        )
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
                "Native SLM %s worker ready (pid=%s, n_ctx=%s, n_batch=%s).",
                self.mode,
                proc.pid,
                ready.get("n_ctx"),
                ready.get("n_batch"),
            )
            return proc
        except NotImplementedError:
            return await self._ensure_popen_worker(cmd)
        except Exception:
            if "proc" in locals() and proc.returncode is None:
                proc.kill()
                await proc.wait()
            raise

    async def _ensure_popen_worker(
        self, cmd: list[str]
    ) -> asyncio.subprocess.Process | subprocess.Popen[bytes] | None:
        proc = subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            if proc.stdout is None:
                raise RuntimeError("worker stdout unavailable")
            raw = await asyncio.wait_for(
                asyncio.to_thread(proc.stdout.readline),
                timeout=self._startup_timeout,
            )
            if not raw:
                raise RuntimeError("worker exited during startup")
            ready = json.loads(raw.decode("utf-8", errors="replace"))
            if ready.get("status") != "READY":
                raise RuntimeError(str(ready.get("reason", "worker startup failed")))
            self._worker = proc
            logger.info(
                "Native SLM %s worker ready via blocking subprocess "
                "(pid=%s, n_ctx=%s, n_batch=%s).",
                self.mode,
                proc.pid,
                ready.get("n_ctx"),
                ready.get("n_batch"),
            )
            return proc
        except Exception:
            if proc.poll() is None:
                proc.kill()
                await asyncio.to_thread(proc.wait)
            raise

    @staticmethod
    def _worker_alive(proc: asyncio.subprocess.Process | subprocess.Popen[bytes]) -> bool:
        if isinstance(proc, subprocess.Popen):
            return proc.poll() is None
        return proc.returncode is None

    @staticmethod
    def _popen_write(proc: subprocess.Popen[bytes], payload: bytes) -> None:
        if proc.stdin is None:
            raise RuntimeError("worker stdin unavailable")
        proc.stdin.write(payload)
        proc.stdin.flush()

    async def _kill_worker(self, reason: str) -> None:
        proc = self._worker
        self._worker = None
        if proc is None or not self._worker_alive(proc):
            return
        logger.warning("Native SLM: killing worker pid=%s (%s).", proc.pid, reason)
        proc.kill()
        try:
            if isinstance(proc, subprocess.Popen):
                await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=5.0)
            else:
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

    def _record_failure(self, reason: str = "") -> bool:
        now = time.monotonic()
        if now - self._last_failure_at > 300.0:
            self._sandbox_failures = 0
        self._last_failure_at = now
        self._sandbox_failures += 1
        reason_l = reason.lower()
        hard_native_failure = any(
            marker in reason_l
            for marker in (
                "ggml_assert",
                "access violation",
                "0xc000001d",
                "winerror -1073741795",
                "illegal instruction",
            )
        )
        if hard_native_failure or self._sandbox_failures >= 3:
            if hard_native_failure:
                self._persist_quarantine(reason)
            self._fallback_mode = os.path.exists(self.model_path)
            self._available = self._fallback_mode
            self._status_detail = (
                f"deterministic fallback after native failure: {reason[:140]}"
                if self._fallback_mode
                else "offline after native failures"
            )
            logger.warning(
                "Native SLM native worker disabled after %s failure(s). Mode is now %s.",
                self._sandbox_failures,
                self.mode,
            )
            return True
        return False

    def _load_quarantine_reason(self) -> str:
        try:
            if not self._quarantine_path.exists():
                return ""
            data = json.loads(self._quarantine_path.read_text(encoding="utf-8"))
            created_at = float(data.get("created_at", 0.0))
            ttl_hours = float(os.environ.get("SOVEREIGN_SLM_QUARANTINE_TTL_HOURS", "168"))
            if ttl_hours > 0 and time.time() - created_at > ttl_hours * 3600:
                return ""
            return str(data.get("reason", "native worker quarantined"))[:160]
        except Exception:
            return "native worker quarantined"

    def _persist_quarantine(self, reason: str) -> None:
        try:
            self._quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "created_at": time.time(),
                "reason": reason[:240],
                "mode": "deterministic_fallback",
            }
            self._quarantine_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug("Native SLM quarantine marker write failed: %s", exc)

    def _fallback_vote(self, context: dict, reason: str) -> dict:
        """Fast deterministic local scorer used when native llama.cpp is unsafe."""

        def as_float(value: Any, default: float) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        belief = max(0.0, min(1.0, as_float(context.get("belief"), 0.5)))
        catalyst = max(0.0, min(1.0, as_float(context.get("catalyst_score"), 0.5)))
        regime = str(context.get("regime", "")).upper()
        dhatu = str(context.get("dhatu_state", "")).upper()
        side = str(context.get("side", "long")).lower()

        score = (belief - 0.5) * 1.35 + (catalyst - 0.5) * 0.75
        if "TREND" in regime:
            score += 0.04
        elif "CRASH" in regime or "PANIC" in regime:
            score -= 0.12
        if any(state in dhatu for state in ("SANKOCHA", "ASANTULANA", "TAMAS")):
            score -= 0.10
        elif any(state in dhatu for state in ("STHIRA", "TEJAS", "PRANA")):
            score += 0.06

        if score > 0.12:
            bias = "BULLISH"
        elif score < -0.12:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        contradicts = (side == "long" and bias == "BEARISH") or (
            side == "short" and bias == "BULLISH"
        )
        vote = "NO" if contradicts else ("ABSTAIN" if bias == "NEUTRAL" else "YES")
        confidence = 0.52 + min(0.26, abs(score) * 0.9)

        return {
            "agent": "Native_SLM",
            "vote": vote,
            "confidence": round(confidence, 3),
            "signal_strength": 1.08 if vote == "YES" else 1.0,
            "risk_flag": str(vote != "YES"),
            "timestamp": context.get("timestamp", time.time_ns()),
            "reason": f"Native SLM {reason}; heuristic bias={bias} score={score:.3f}",
            "bias": bias,
            "agent_count": 1,
        }

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
        self._fallback_mode = False
        self._compat_mode = False
        self._status_detail = "offline"
