"""Fail-closed production promotion readiness from auditable evidence artifacts."""

from __future__ import annotations

from typing import Any


def _block(blockers: list[str], condition: bool, message: str) -> None:
    if not condition:
        blockers.append(message)


def evaluate_promotion_readiness(
    *,
    execution_evidence: dict[str, Any],
    reliability_probe: dict[str, Any],
    regime_replay: dict[str, Any],
    soak_summary: dict[str, Any],
    paper_performance: dict[str, Any],
    min_modern_intents: int = 30,
    min_closed_paper_trades: int = 30,
    min_profit_factor: float = 1.20,
    max_drawdown_pct: float = 0.10,
    min_soak_cycles: int = 3,
) -> dict[str, Any]:
    """Return an auditable paper-to-production gate without optimistic defaults."""
    blockers: list[str] = []
    lineage = execution_evidence.get("lineage", {})
    costs = execution_evidence.get("costs", {})
    audit = execution_evidence.get("audit", {})
    soak_cycles = soak_summary.get("cycles", [])
    intents = int(lineage.get("intents", 0) or 0)
    filled_intents = int(lineage.get("filled_intents", 0) or 0)
    commission_reports = int(costs.get("commission_reports", 0) or 0)
    performance = paper_performance.get("metrics", {})
    closed_paper_trades = int(performance.get("trades", 0) or 0)

    _block(blockers, audit.get("valid") is True, "execution audit chain is not valid")
    _block(
        blockers,
        reliability_probe.get("passed") is True,
        "deterministic reliability probe has not passed",
    )
    _block(
        blockers,
        regime_replay.get("passed") is True,
        "deterministic regime replay has not passed",
    )
    _block(
        blockers,
        regime_replay.get("promotion_eligible") is False,
        "synthetic replay is incorrectly marked promotion eligible",
    )
    _block(
        blockers,
        soak_summary.get("passed") is True and len(soak_cycles) >= min_soak_cycles,
        f"restart soak requires {min_soak_cycles} passing cycles",
    )
    _block(
        blockers,
        intents >= min_modern_intents,
        f"modern paper execution lineage requires {min_modern_intents} intents; found {intents}",
    )
    _block(
        blockers,
        int(lineage.get("unmatched_lineage_events", 0) or 0) == 0,
        "unmatched broker lineage events remain",
    )
    _block(
        blockers,
        filled_intents > 0,
        "no modern paper fills recorded",
    )
    _block(
        blockers,
        commission_reports >= filled_intents,
        "commission coverage is incomplete for modern fills",
    )
    _block(
        blockers,
        int(costs.get("observed_slippage_events", 0) or 0) >= filled_intents,
        "slippage coverage is incomplete for modern fills",
    )
    _block(
        blockers,
        paper_performance.get("source") == "sqlite_closed_paper_trades",
        "paper performance artifact source is not trusted",
    )
    _block(
        blockers,
        closed_paper_trades >= min_closed_paper_trades,
        f"closed paper performance requires {min_closed_paper_trades} trades; found {closed_paper_trades}",
    )
    _block(
        blockers,
        float(performance.get("expectancy_net", 0.0) or 0.0) > 0,
        "closed paper expectancy is not positive after costs",
    )
    _block(
        blockers,
        float(performance.get("profit_factor", 0.0) or 0.0) >= min_profit_factor,
        f"closed paper profit factor is below {min_profit_factor:.2f}",
    )
    _block(
        blockers,
        float(performance.get("max_drawdown_pct", 1.0) or 0.0) <= max_drawdown_pct,
        f"closed paper max drawdown exceeds {max_drawdown_pct:.1%}",
    )

    return {
        "approved": not blockers,
        "mode": "paper_to_production_gate",
        "blockers": blockers,
        "evidence": {
            "audit_valid": audit.get("valid") is True,
            "reliability_probe_passed": reliability_probe.get("passed") is True,
            "regime_replay_passed": regime_replay.get("passed") is True,
            "restart_soak_cycles": len(soak_cycles),
            "modern_intents": intents,
            "filled_intents": filled_intents,
            "commission_reports": commission_reports,
            "observed_slippage_events": int(costs.get("observed_slippage_events", 0) or 0),
            "unmatched_lineage_events": int(lineage.get("unmatched_lineage_events", 0) or 0),
            "closed_paper_trades": closed_paper_trades,
            "paper_expectancy_net": float(performance.get("expectancy_net", 0.0) or 0.0),
            "paper_profit_factor": float(performance.get("profit_factor", 0.0) or 0.0),
            "paper_max_drawdown_pct": float(performance.get("max_drawdown_pct", 0.0) or 0.0),
        },
    }
