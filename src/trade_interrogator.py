"""Trade Interrogator: self-questioning engine before every trade.

Forces every trade proposal to answer a checklist of market-context questions.
If the system cannot answer confidently, the trade is blocked.  Designed to
prevent low-conviction entries and enforce adaptive, present-aware decision
making.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from market_microstructure import (
    MarketMicrostructure,
    get_global_microstructure,
    is_liquid,
)

logger = logging.getLogger(__name__)


@dataclass
class InterrogationResult:
    """Result of questioning a trade proposal."""

    score: float  # 0.0 to 1.0
    passed: bool
    reasons: list[str]
    details: dict[str, Any]


class TradeInterrogator:
    """Question every trade before it is allowed to execute."""

    def __init__(
        self,
        microstructure: MarketMicrostructure | None = None,
        min_score: float = 0.65,
        min_liquid_spread_pct: float = 0.002,
        max_vwap_deviation: float = 0.01,
        min_rr: float = 1.1,
    ):
        self.microstructure = (
            microstructure if microstructure is not None else get_global_microstructure()
        )
        self.min_score = min_score
        self.min_liquid_spread_pct = min_liquid_spread_pct
        self.max_vwap_deviation = max_vwap_deviation
        self.min_rr = min_rr

    def interrogate(
        self,
        symbol: str,
        pattern: Any,
        proposal: dict[str, Any],
        *,
        current_regime: str = "UNKNOWN",
        pattern_stats: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> InterrogationResult:
        """Score a trade proposal by answering the hawk-eye checklist.

        Returns a score from 0.0 to 1.0.  If score < min_score, the trade is
        blocked and `passed` is False.
        """
        symbol = symbol.upper()
        reasons: list[str] = []
        details: dict[str, Any] = {}
        score = 0.0
        max_possible = 0.0

        # --- Q1: What regime is the market in right now? ---
        max_possible += 1.0
        regime_ok = current_regime not in ("UNKNOWN", "RISK_OFF", "PANIC")
        details["regime"] = current_regime
        if regime_ok:
            score += 1.0
        else:
            reasons.append(f"Regime is {current_regime} — hostile to new entries")

        # --- Q2: Is the market liquid and tradeable? ---
        max_possible += 1.0
        snap = self.microstructure.get_snapshot(symbol)
        liquid = snap.last_price > 0 and (
            snap.spread_pct < self.min_liquid_spread_pct and snap.tape_speed_30s > 0.5
        )
        details["microstructure"] = self.microstructure.summary(symbol)
        if liquid:
            score += 1.0
        else:
            reasons.append(
                f"Illiquid: spread={snap.spread_pct:.4%}, tape_speed={snap.tape_speed_30s:.2f}/s"
            )

        # --- Q3: Is the order flow supporting this direction? ---
        max_possible += 1.0
        imbalance = snap.book_imbalance
        direction = proposal.get("direction", "LONG")
        flow_aligned = (
            (direction == "LONG" and imbalance > 0.1)
            or (direction == "SHORT" and imbalance < -0.1)
            or abs(imbalance) < 0.3  # neutral is acceptable
        )
        details["order_flow_aligned"] = flow_aligned
        details["book_imbalance"] = imbalance
        if flow_aligned:
            score += 1.0
        else:
            reasons.append(
                f"Order flow against {direction}: imbalance={imbalance:.2f}"
            )

        # --- Q4: Is price too far from VWAP (chasing)? ---
        max_possible += 1.0
        vwap_dev = abs(self.microstructure.get_vwap_deviation(symbol))
        details["vwap_deviation"] = vwap_dev
        if vwap_dev <= self.max_vwap_deviation:
            score += 1.0
        else:
            reasons.append(f"Chasing VWAP: deviation={vwap_dev:.4%}")

        # --- Q5: Has this pattern worked in this regime recently? ---
        max_possible += 1.0
        pattern_name = getattr(pattern, "name", "UNKNOWN")
        stats = pattern_stats or {}
        recent_wr = float(stats.get("win_rate", 0.5))
        sample_size = int(stats.get("sample_size", 0))
        edge_ok = recent_wr >= 0.45 and sample_size >= 5
        details["pattern"] = pattern_name
        details["pattern_stats"] = stats
        if edge_ok:
            score += 1.0
        else:
            if sample_size < 5:
                reasons.append(f"Insufficient sample size for {pattern_name} ({sample_size})")
            else:
                reasons.append(f"Pattern {pattern_name} has weak edge ({recent_wr:.1%} WR)")

        # --- Q6: Is the risk/reward acceptable after costs? ---
        max_possible += 1.0
        entry = getattr(pattern, "entry", 0.0) or proposal.get("entry_price", 0.0)
        stop = getattr(pattern, "stop", 0.0) or proposal.get("stop_price", 0.0)
        target = getattr(pattern, "target", 0.0) or proposal.get("target_price", 0.0)
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr = reward / risk if risk > 0 else 0.0
        details["risk_reward"] = rr
        if rr >= self.min_rr:
            score += 1.0
        else:
            reasons.append(f"R:R too low: {rr:.2f} < {self.min_rr}")

        # --- Q7: Is there abnormal volume confirming the move? ---
        max_possible += 1.0
        details["abnormal_volume"] = snap.abnormal_volume
        if snap.abnormal_volume:
            score += 1.0
        else:
            # Neutral, not penalised — many valid trades lack volume spikes.
            score += 0.5

        # Normalise to 0.0–1.0.
        final_score = score / max_possible if max_possible > 0 else 0.0
        # Any hard-veto reason makes the trade ineligible regardless of the score.
        hard_veto_reasons = [
            r
            for r in reasons
            if any(
                key in r
                for key in (
                    "Regime",
                    "Illiquid",
                    "Order flow",
                    "VWAP",
                    "R:R",
                    "weak edge",
                    "Insufficient sample",
                )
            )
        ]
        threshold = min_score if min_score is not None else self.min_score
        passed = not hard_veto_reasons and final_score >= threshold

        if hard_veto_reasons:
            reasons.insert(0, f"Hard veto: {' | '.join(hard_veto_reasons)}")
        elif not passed:
            reasons.insert(
                0,
                f"Interrogator score {final_score:.2f} < threshold {threshold}",
            )
        else:
            reasons.append(f"Interrogator score {final_score:.2f} passed")

        logger.debug(
            "TradeInterrogator [%s] %s score=%.2f passed=%s",
            symbol,
            pattern_name,
            final_score,
            passed,
        )
        return InterrogationResult(
            score=final_score,
            passed=passed,
            reasons=reasons,
            details=details,
        )


# Global instance for easy access.
_GLOBAL_INTERROGATOR: TradeInterrogator | None = None


def get_global_interrogator() -> TradeInterrogator:
    global _GLOBAL_INTERROGATOR
    if _GLOBAL_INTERROGATOR is None:
        _GLOBAL_INTERROGATOR = TradeInterrogator()
    return _GLOBAL_INTERROGATOR


def set_global_interrogator(interrogator: TradeInterrogator) -> None:
    global _GLOBAL_INTERROGATOR
    _GLOBAL_INTERROGATOR = interrogator


def reset_global_interrogator() -> None:
    global _GLOBAL_INTERROGATOR
    _GLOBAL_INTERROGATOR = None


def interrogate(
    symbol: str,
    pattern: Any,
    proposal: dict[str, Any],
    **kwargs: Any,
) -> InterrogationResult:
    return get_global_interrogator().interrogate(symbol, pattern, proposal, **kwargs)


__all__ = [
    "TradeInterrogator",
    "InterrogationResult",
    "get_global_interrogator",
    "set_global_interrogator",
    "reset_global_interrogator",
    "interrogate",
]
