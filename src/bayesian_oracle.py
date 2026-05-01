"""
Upgrades DhatuOracle with proper Bayesian regime inference.
P(regime|evidence) updated on every new data point.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BayesianState:
    regime: str
    confidence: float
    posteriors: dict[str, float]
    dhatu: str
    summary: str


REGIME_DHATU_MAP = {
    "BULL":     "Vriddhi (Growth)",
    "BEAR":     "Kshaya (Decay)",
    "SIDEWAYS": "Sthira (Stable)",
    "HIGH_VOL": "Chala (Volatile)",
}

# Likelihood table: P(evidence_bucket | regime)
# Learned from market history. Values are calibrated probabilities.
# Each row: [BULL, BEAR, SIDEWAYS, HIGH_VOL]
LIKELIHOODS = {
    # (feature, bucket): [P(feat=bucket|BULL), P(feat=bucket|BEAR), P(feat=bucket|SIDEWAYS), P(feat=bucket|HIGH_VOL)]
    "momentum_positive":    [0.70, 0.20, 0.45, 0.40],
    "momentum_negative":    [0.30, 0.80, 0.55, 0.60],
    "vix_low":              [0.65, 0.15, 0.55, 0.05],
    "vix_high":             [0.15, 0.70, 0.20, 0.90],
    "volume_expanding":     [0.60, 0.55, 0.30, 0.65],
    "volume_contracting":   [0.40, 0.45, 0.70, 0.35],
    "breadth_positive":     [0.72, 0.18, 0.48, 0.35],
    "breadth_negative":     [0.28, 0.82, 0.52, 0.65],
}

REGIMES = ["BULL", "BEAR", "SIDEWAYS", "HIGH_VOL"]


class BayesianOracle:
    """
    Bayesian regime classifier. Updates beliefs on every new market observation.
    Provides calibrated confidence scores (not LLM hallucinations).
    Usage:
        oracle = BayesianOracle()
        state = oracle.update(prices, volumes, vix)
    """

    def __init__(self):
        # Uniform prior — no initial bias
        self._priors: dict[str, float] = {r: 0.25 for r in REGIMES}
        self._history: list[BayesianState] = []
        self._update_count: int = 0

    def update(self, prices: np.ndarray, volumes: np.ndarray,
               vix: float = 15.0) -> BayesianState:
        """
        Bayesian update: P(regime|evidence) ∝ P(evidence|regime) * P(regime)
        """
        evidence = self._extract_evidence(prices, volumes, vix)
        if not evidence:
            return self.current_state or self._get_initial_state()

        posteriors = self._bayes_update(evidence)

        # MAP estimate
        best_regime = max(posteriors, key=posteriors.__getitem__)
        confidence  = posteriors[best_regime]

        # Decay priors toward uniform slightly to avoid over-certainty
        self._priors = {r: 0.95 * posteriors[r] + 0.05 * 0.25 for r in REGIMES}

        state = BayesianState(
            regime     = best_regime,
            confidence = round(confidence, 4),
            posteriors = {r: round(v, 4) for r, v in posteriors.items()},
            dhatu      = REGIME_DHATU_MAP.get(best_regime, "Sthiti (Persistence)"),
            summary    = self._build_summary(best_regime, confidence, evidence),
        )
        self._history.append(state)
        if len(self._history) > 500:
            self._history.pop(0)
        self._update_count += 1
        return state

    def _extract_evidence(self, prices: np.ndarray, volumes: np.ndarray,
                           vix: float) -> list[str]:
        """Convert raw market data into discrete evidence buckets."""
        evidence = []
        if len(prices) >= 21:
            returns = np.diff(np.log(prices + 1e-10))
            momentum = float(np.sum(returns[-21:]))
            evidence.append("momentum_positive" if momentum > 0 else "momentum_negative")

        evidence.append("vix_high" if vix > 20.0 else "vix_low")

        if len(volumes) >= 10:
            vol_trend = float(np.mean(volumes[-5:])) / (float(np.mean(volumes[-10:])) + 1e-10)
            evidence.append("volume_expanding" if vol_trend > 1.05 else "volume_contracting")

        # Breadth proxy: ratio of up-days in last 10
        if len(prices) >= 11:
            up_days = sum(1 for r in np.diff(prices[-11:]) if r > 0)
            evidence.append("breadth_positive" if up_days >= 6 else "breadth_negative")

        return evidence

    def _bayes_update(self, evidence: list[str]) -> dict[str, float]:
        """Apply Bayes theorem for each piece of evidence sequentially."""
        posteriors = dict(self._priors)

        for ev in evidence:
            if ev not in LIKELIHOODS:
                continue
            likelihoods = dict(zip(REGIMES, LIKELIHOODS[ev], strict=False))
            # Unnormalized update
            unnorm = {r: posteriors[r] * likelihoods[r] for r in REGIMES}

            total = sum(unnorm.values())
            if total < 1e-15:
                # If all likelihoods are zero, don't update this step
                continue

            posteriors = {r: unnorm[r] / total for r in REGIMES}

        return posteriors

    def _build_summary(self, regime: str, conf: float, evidence: list[str]) -> str:
        ev_str = ", ".join(evidence[:3])
        return (f"Bayesian Oracle: {regime} @ {conf:.1%} | "
                f"Evidence: {ev_str} | Updates: {self._update_count}")

    def _get_initial_state(self) -> BayesianState:
        """Returns a neutral initial state for cold-starts."""
        return BayesianState(
            regime="SIDEWAYS",
            confidence=0.25,
            posteriors=dict(self._priors),
            dhatu="Sthiti (Persistence)",
            summary="Bayesian Oracle: Cold Start | Awaiting Market Scents..."
        )

    @property
    def current_state(self) -> Optional[BayesianState]:
        return self._history[-1] if self._history else None

    def get_api_dict(self) -> dict:
        """Returns dict compatible with existing api_server state format."""
        s = self.current_state
        if s is None:
            return {"dhatu": "Sthiti (Persistence)", "confidence": 0.0,
                    "regime": "UNKNOWN", "summary": "No data yet"}
        return {
            "dhatu":       s.dhatu,
            "confidence":  s.confidence,
            "regime":      s.regime,
            "theme":       s.regime,
            "summary":     s.summary,
            "posteriors":  s.posteriors,
        }
