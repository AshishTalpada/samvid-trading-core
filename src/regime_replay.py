"""Deterministic closed-market replay packs for safety and observability verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from agent_c_ibkr import BlackSwanProtocol
from strategy_promotion import evaluate_strategy_promotion


@dataclass(frozen=True)
class ReplayScenario:
    name: str
    regime: str
    pnl_values: tuple[float, ...]
    vix: float
    drawdown_pct: float
    expected_policy: str


DEFAULT_SCENARIOS = (
    ReplayScenario(
        name="trend_up_control",
        regime="BULL",
        pnl_values=(2.0, -1.0) * 15,
        vix=16.0,
        drawdown_pct=0.01,
        expected_policy="NORMAL",
    ),
    ReplayScenario(
        name="trend_down_control",
        regime="BEAR",
        pnl_values=(1.8, -1.0) * 15,
        vix=24.0,
        drawdown_pct=0.03,
        expected_policy="NORMAL",
    ),
    ReplayScenario(
        name="choppy_cost_pressure",
        regime="CHOPPY",
        pnl_values=(0.6, -0.8) * 15,
        vix=22.0,
        drawdown_pct=0.04,
        expected_policy="NORMAL",
    ),
    ReplayScenario(
        name="flash_crash_freeze",
        regime="VOLATILE",
        pnl_values=(-1.0, -1.5, -2.0),
        vix=65.0,
        drawdown_pct=0.08,
        expected_policy="FREEZE",
    ),
    ReplayScenario(
        name="drawdown_freeze",
        regime="DRAWDOWN",
        pnl_values=(-1.0, -1.0, -1.0),
        vix=28.0,
        drawdown_pct=0.15,
        expected_policy="FREEZE",
    ),
)


def _max_drawdown(pnl_values: Iterable[float], starting_equity: float = 100.0) -> float:
    equity = float(starting_equity)
    peak = equity
    max_drawdown = 0.0
    for pnl in pnl_values:
        equity += float(pnl)
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / max(peak, 1e-12))
    return max_drawdown


def run_regime_replay_pack(
    scenarios: Iterable[ReplayScenario] = DEFAULT_SCENARIOS,
) -> dict[str, Any]:
    """Run deterministic safety scenarios and return a machine-readable artifact."""
    protocol = BlackSwanProtocol()
    results = []
    for scenario in scenarios:
        policy = protocol.check(vix=scenario.vix, drawdown_pct=scenario.drawdown_pct)
        promotion = evaluate_strategy_promotion(scenario.pnl_values)
        results.append(
            {
                **asdict(scenario),
                "policy": policy,
                "policy_match": policy == scenario.expected_policy,
                "max_drawdown": _max_drawdown(scenario.pnl_values),
                "promotion_metrics": promotion["metrics"],
            }
        )

    required_regimes = {"BULL", "BEAR", "CHOPPY", "VOLATILE", "DRAWDOWN"}
    covered_regimes = {result["regime"] for result in results}
    missing_regimes = sorted(required_regimes - covered_regimes)
    policy_failures = sorted(
        result["name"] for result in results if not result["policy_match"]
    )
    return {
        "mode": "synthetic_safety_replay",
        "promotion_eligible": False,
        "operator_note": (
            "Synthetic replay verifies safety behavior and evidence plumbing only. "
            "It must never authorize live strategy promotion."
        ),
        "passed": not missing_regimes and not policy_failures,
        "coverage": {
            "required_regimes": sorted(required_regimes),
            "covered_regimes": sorted(covered_regimes),
            "missing_regimes": missing_regimes,
        },
        "policy_failures": policy_failures,
        "scenarios": results,
    }
