"""Runtime health scoring for production monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: str
    detail: str = ""
    critical: bool = True

    @property
    def is_online(self) -> bool:
        return self.status.upper() in {"ONLINE", "ACTIVE", "NATIVE", "FALLBACK", "CONNECTED"}

    @property
    def is_degraded(self) -> bool:
        return self.status.upper() in {"DEGRADED", "FALLBACK", "DELAYED", "PARKED", "PAUSED"}


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
