"""Deterministic evidence gate for promoting shadow strategies."""

from __future__ import annotations

from typing import Any, Iterable


def evaluate_strategy_promotion(
    pnl_values: Iterable[float],
    *,
    min_trades: int = 30,
    min_expectancy: float = 0.0,
    min_profit_factor: float = 1.20,
    max_consecutive_losses: int = 5,
) -> dict[str, Any]:
    """Return an auditable promotion decision from realized shadow P&L."""
    pnls = [float(value) for value in pnl_values]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    expectancy = sum(pnls) / len(pnls) if pnls else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if wins else 0.0

    longest_loss_streak = 0
    current_loss_streak = 0
    for pnl in pnls:
        if pnl < 0:
            current_loss_streak += 1
            longest_loss_streak = max(longest_loss_streak, current_loss_streak)
        else:
            current_loss_streak = 0

    reasons: list[str] = []
    if len(pnls) < min_trades:
        reasons.append(f"sample size {len(pnls)}/{min_trades}")
    if expectancy <= min_expectancy:
        reasons.append(f"expectancy {expectancy:.4f} <= {min_expectancy:.4f}")
    if profit_factor < min_profit_factor:
        reasons.append(f"profit factor {profit_factor:.3f} < {min_profit_factor:.3f}")
    if longest_loss_streak > max_consecutive_losses:
        reasons.append(
            f"loss streak {longest_loss_streak} > {max_consecutive_losses}"
        )

    return {
        "approved": not reasons,
        "reasons": reasons,
        "metrics": {
            "trades": len(pnls),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(pnls) if pnls else 0.0,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "longest_loss_streak": longest_loss_streak,
        },
    }
