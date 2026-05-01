"""
src/llm_circuit_breaker.py — LLM API Circuit Breaker

Wraps any async LLM call with:
  1. A hard timeout (default 4s) — if the API is slow, we don't wait.
  2. Automatic fallback to a pure quantitative signal.
  3. Decision Ledger flagging — every fallback is recorded as "FALLBACK_MODE".

Usage:
    from llm_circuit_breaker import llm_call_with_fallback

    result = await llm_call_with_fallback(
        coro=some_mind.analyse(context),
        fallback_fn=lambda: {"signal": "HOLD", "confidence": 0.5, "source": "quant_fallback"},
        label="MindUltrathink.analyse",
        timeout_s=4.0,
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger("LLMCircuitBreaker")


class CircuitState:
    CLOSED = "CLOSED"  # Normal — LLM calls go through
    OPEN = "OPEN"  # Tripped — all calls use fallback instantly
    HALF_OPEN = "HALF_OPEN"  # Probing — one call allowed to test recovery


class LLMCircuitBreaker:
    """
    Per-mind circuit breaker with sliding-window failure tracking.

    Rules:
      - CLOSED  → If a call times out or raises, failure_count++
      - CLOSED  → If failure_count >= threshold within window → trip to OPEN
      - OPEN    → All calls immediately return fallback; try recovery after cooldown_s
      - HALF_OPEN → One probe call. Success → CLOSED. Failure → back to OPEN.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        window_s: float = 60.0,
        cooldown_s: float = 30.0,
        default_timeout_s: float = 4.0,
    ) -> None:
        self._threshold = failure_threshold
        self._window = window_s
        self._cooldown = cooldown_s
        self._timeout = default_timeout_s

        self._state = CircuitState.CLOSED
        self._failures: deque[float] = deque()  # timestamps
        self._tripped_at: float = 0.0
        self._total_timeouts: int = 0
        self._total_fallbacks: int = 0

    @property
    def state(self) -> str:
        return self._state

    def _prune_failures(self) -> None:
        """Evict failure timestamps outside the sliding window."""
        now = time.monotonic()
        while self._failures and (now - self._failures[0]) > self._window:
            self._failures.popleft()

    def _record_failure(self) -> None:
        self._failures.append(time.monotonic())
        self._prune_failures()
        if len(self._failures) >= self._threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._tripped_at = time.monotonic()
        self._total_fallbacks += 1
        logger.critical(
            f"LLM Circuit Breaker TRIPPED — {len(self._failures)} failures in "
            f"{self._window}s. All LLM calls will use fallback for {self._cooldown}s."
        )

    def _maybe_recover(self) -> bool:
        """Check if cooldown has passed and allow a probe."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._tripped_at >= self._cooldown:
                self._state = CircuitState.HALF_OPEN
                logger.info("LLM Circuit Breaker: Entering HALF_OPEN — probing recovery...")
                return True
        return False

    async def call(
        self,
        coro: Coroutine,
        fallback_fn: Callable[[], Any],
        label: str = "LLM",
        timeout_s: float | None = None,
    ) -> tuple[Any, bool]:
        """
        Execute the LLM coroutine with circuit breaker protection.

        Returns:
            (result, is_fallback) — is_fallback=True when the fallback was used.
        """
        timeout = timeout_s or self._timeout

        # --- OPEN: Skip call entirely ---
        if self._state == CircuitState.OPEN:
            self._maybe_recover()
            if self._state == CircuitState.OPEN:
                self._total_fallbacks += 1
                logger.warning(f"CB [{label}]: OPEN — returning fallback instantly.")
                return fallback_fn(), True

        # --- CLOSED or HALF_OPEN: Attempt the call ---
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            latency_ms = (time.monotonic() - t0) * 1000

            if self._state == CircuitState.HALF_OPEN:
                # Probe succeeded — close the breaker
                self._state = CircuitState.CLOSED
                self._failures.clear()
                logger.info(
                    f"CB [{label}]: HALF_OPEN probe succeeded — CLOSED. Latency: {latency_ms:.1f}ms"
                )

            if latency_ms > 1500:
                logger.warning(
                    f"CB [{label}]: Slow response {latency_ms:.0f}ms (threshold: {timeout * 1000:.0f}ms)"
                )

            return result, False

        except asyncio.TimeoutError:
            self._total_timeouts += 1
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error(
                f"CB [{label}]: TIMEOUT after {latency_ms:.0f}ms "
                f"(limit: {timeout * 1000:.0f}ms). Using fallback."
            )
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._tripped_at = time.monotonic()
            else:
                self._record_failure()
            return fallback_fn(), True

        except Exception as e:
            logger.error(f"CB [{label}]: Exception — {e}. Using fallback.")
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._tripped_at = time.monotonic()
            else:
                self._record_failure()
            return fallback_fn(), True

    @property
    def stats(self) -> dict:
        self._prune_failures()
        return {
            "state": self._state,
            "recent_failures": len(self._failures),
            "total_timeouts": self._total_timeouts,
            "total_fallbacks": self._total_fallbacks,
            "threshold": self._threshold,
        }


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


async def llm_call_with_fallback(
    coro: Coroutine,
    fallback_fn: Callable[[], Any],
    breaker: LLMCircuitBreaker,
    label: str = "LLM",
    timeout_s: float = 4.0,
    symbol: str = "",
) -> Any:
    """
    Convenience wrapper that runs `coro` through `breaker`.
    If the fallback fires, it also logs to the DecisionLedger.

    Returns the result (real or fallback).
    """
    from decision_ledger import LEDGER

    result, is_fallback = await breaker.call(coro, fallback_fn, label=label, timeout_s=timeout_s)

    if is_fallback:
        LEDGER.record_veto(
            symbol=symbol or "SYSTEM",
            reason=f"FALLBACK_MODE: {label} timed out or circuit open",
            triggered_by="llm_circuit_breaker",
            meta={
                "breaker_stats": breaker.stats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return result


# ---------------------------------------------------------------------------
# Global breakers — one per "mind class" category
# ---------------------------------------------------------------------------

# Breaker for high-stakes reasoning (UltraThink, Architect)
HEAVY_BREAKER = LLMCircuitBreaker(
    failure_threshold=2, window_s=60.0, cooldown_s=60.0, default_timeout_s=5.0
)

# Breaker for background analysis (Observer, Evolution, Experiment)
LIGHT_BREAKER = LLMCircuitBreaker(
    failure_threshold=3, window_s=120.0, cooldown_s=30.0, default_timeout_s=3.0
)
