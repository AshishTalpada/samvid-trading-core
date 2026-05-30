"""Runtime health scoring for production monitoring."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: str
    detail: str = ""
    critical: bool = True

    @property
    def is_online(self) -> bool:
        return self.status.upper() in {
            "ONLINE",
            "ACTIVE",
            "NATIVE",
            "COMPAT",
            "FALLBACK",
            "CONNECTED",
        }

    @property
    def is_degraded(self) -> bool:
        return self.status.upper() in {"DEGRADED", "FALLBACK", "DELAYED", "PARKED", "PAUSED"}

    @property
    def normalized_status(self) -> str:
        return self.status.upper()


def market_data_health(
    freshness_proofs: Mapping[str, float] | None,
    *,
    market_open: bool,
    max_age_sec: float = 60.0,
    now_monotonic: float | None = None,
) -> ComponentHealth:
    """Score the scanner data plane from recent verified bar evidence."""
    if not market_open:
        return ComponentHealth("market_data", "PAUSED", "US equity market closed", critical=True)
    if not freshness_proofs:
        return ComponentHealth(
            "market_data",
            "DELAYED",
            "awaiting first verified live bar",
            critical=True,
        )

    now = time.monotonic() if now_monotonic is None else float(now_monotonic)
    newest_age = max(0.0, now - max(float(ts) for ts in freshness_proofs.values()))
    bounded_max_age = max(5.0, min(float(max_age_sec), 900.0))
    if newest_age > bounded_max_age:
        return ComponentHealth(
            "market_data",
            "DELAYED",
            f"latest verified live bar proof is {newest_age:.1f}s old",
            critical=True,
        )
    return ComponentHealth(
        "market_data",
        "ONLINE",
        f"verified_symbols={len(freshness_proofs)}, newest_proof_age={newest_age:.1f}s",
        critical=True,
    )


def _score_health(
    components: list[ComponentHealth],
    *,
    dropped_ticks: int,
    critical_offline: list[str],
    degraded: list[str],
) -> tuple[int, str, list[str]]:
    score = 100
    actions: list[str] = []

    for component in components:
        status = component.normalized_status
        if component.name in critical_offline:
            score -= 45
            actions.append(f"Restore critical component: {component.name}")
            continue
        if component.name in degraded:
            penalty = 18 if component.critical else 7
            if status == "FALLBACK":
                penalty += 5 if component.critical else 3
                actions.append(f"Investigate fallback mode: {component.name}")
            elif status == "PAUSED":
                actions.append(f"Confirm pause is expected: {component.name}")
            else:
                actions.append(f"Review degraded component: {component.name}")
            score -= penalty
        elif not component.is_online and not component.is_degraded:
            penalty = 20 if component.critical else 5
            score -= penalty
            actions.append(f"Bring optional component online: {component.name}")

    if dropped_ticks > 0:
        tick_penalty = min(20, max(3, dropped_ticks // 1000 + 3))
        score -= tick_penalty
        actions.append(f"Reduce dropped market-data ticks: {dropped_ticks}")

    score = max(0, min(100, score))
    if critical_offline:
        readiness = "BLOCKED"
    elif degraded or dropped_ticks > 0:
        readiness = "DEGRADED_READY" if score >= 75 else "DEGRADED_RISK"
    elif score >= 92:
        readiness = "READY"
    elif score >= 75:
        readiness = "DEGRADED_READY"
    else:
        readiness = "DEGRADED_RISK"
    return score, readiness, actions[:8]


def build_health_snapshot(
    components: list[ComponentHealth],
    *,
    mode: str,
    state: str,
    dropped_ticks: int = 0,
    open_positions: int = 0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact fund-style runtime health snapshot."""
    critical_offline = [
        c.name for c in components if c.critical and not c.is_online and not c.is_degraded
    ]
    degraded = [c.name for c in components if c.is_degraded]
    readiness_score, readiness, action_items = _score_health(
        components,
        dropped_ticks=int(dropped_ticks),
        critical_offline=critical_offline,
        degraded=degraded,
    )
    if critical_offline:
        overall = "OFFLINE"
    elif degraded or dropped_ticks > 0:
        overall = "DEGRADED"
    else:
        overall = "ONLINE"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall": overall,
        "mode": mode,
        "state": state,
        "critical_offline": critical_offline,
        "degraded": degraded,
        "readiness": readiness,
        "readiness_score": readiness_score,
        "action_items": action_items,
        "operator_summary": (
            f"{readiness} ({readiness_score}/100): "
            f"{len(critical_offline)} critical offline, {len(degraded)} degraded, "
            f"{int(dropped_ticks)} dropped ticks"
        ),
        "dropped_ticks": int(dropped_ticks),
        "open_positions": int(open_positions),
        "components": {
            c.name: {
                "status": c.status,
                "detail": c.detail,
                "critical": c.critical,
            }
            for c in components
        },
        "extra": extra or {},
    }
