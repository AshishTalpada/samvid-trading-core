"""Instruction-safe SLM compatibility worker.

This process implements the same newline-delimited JSON protocol as
``neural_sandbox.py --worker`` without importing llama.cpp. It is used when
the native GGML binary is quarantined for CPU/runtime incompatibility.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score_context(context: dict[str, Any]) -> tuple[str, float]:
    belief = max(0.0, min(1.0, _as_float(context.get("belief"), 0.5)))
    catalyst = max(0.0, min(1.0, _as_float(context.get("catalyst_score"), 0.5)))
    regime = str(context.get("regime", "")).upper()
    dhatu = str(context.get("dhatu_state", "")).upper()
    pattern = str(context.get("pattern", "")).upper()

    score = (belief - 0.5) * 1.35 + (catalyst - 0.5) * 0.75
    if "TREND" in regime or "BULL" in regime:
        score += 0.05
    if "CRASH" in regime or "PANIC" in regime:
        score -= 0.16
    if any(token in pattern for token in ("BULL", "BREAKOUT", "MOMENTUM")):
        score += 0.04
    if any(token in pattern for token in ("BEAR", "BREAKDOWN", "DISTRIBUTION")):
        score -= 0.04
    if any(state in dhatu for state in ("SANKOCHA", "ASANTULANA", "TAMAS", "ABHAVA")):
        score -= 0.12
    elif any(state in dhatu for state in ("STHIRA", "TEJAS", "PRANA", "SAMYOGA")):
        score += 0.07

    if score > 0.12:
        return "BULLISH", score
    if score < -0.12:
        return "BEARISH", score
    return "NEUTRAL", score


def run_worker() -> None:
    print(
        json.dumps(
            {
                "status": "READY",
                "backend": "compat_heuristic",
                "n_ctx": 0,
                "n_batch": 0,
                "n_ubatch": 0,
            }
        ),
        flush=True,
    )
    for line in sys.stdin:
        try:
            request = json.loads(line)
            bias, score = _score_context(dict(request.get("context") or {}))
            print(
                json.dumps(
                    {
                        "id": request.get("id"),
                        "status": "SUCCESS",
                        "text": bias,
                        "score": round(score, 6),
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "id": request.get("id") if "request" in locals() else None,
                        "status": "ERROR",
                        "reason": str(exc),
                    },
                    separators=(",", ":"),
                ),
                flush=True,
            )


if __name__ == "__main__":
    run_worker()
