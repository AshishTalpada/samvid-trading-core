"""
Replaces LLM agent opinions with statistically validated signals.
Each signal is independently testable and has a known theoretical basis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from config import STARTING_CAPITAL_CAD

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    name: str
    score: float  # -1.0 (strong sell) to +1.0 (strong buy)
    confidence: float  # 0.0 to 1.0
    vote: str  # 'BUY' | 'SELL' | 'NEUTRAL'
    meta: dict = field(default_factory=dict)

    def to_vote(self) -> str:
        if self.score > 0.05 and self.confidence > 0.5:
            return "BUY"
        if self.score < -0.05 and self.confidence > 0.5:
            return "SELL"
        return "NEUTRAL"


class RegimeFilter:
    """
    Hidden Markov Model regime detection.
    Identifies Bull / Bear / Sideways regimes from price returns.
    Only passes BUY signals during Bull regime, SELL during Bear.
    Theory: AQR, Bridgewater use HMM-based regime switching.
    """

    def __init__(self, n_regimes: int = 3):
        self.n_regimes = n_regimes
        self._model = None
        self._regime_labels: dict[int, str] = {}

    def fit(self, prices: np.ndarray) -> None:
        """Fit HMM on historical log-returns. Call during backtesting."""
        try:
            from hmmlearn import hmm

            returns = np.diff(np.log(np.abs(prices) + 1e-10)).reshape(-1, 1)
            returns = returns[np.isfinite(returns).all(axis=1)]

            if len(returns) < 100:
                logger.warning(f"RegimeFilter: insufficient data ({len(returns)} < 100)")
                return

            # Statistical Floor: Reject if variance is too low (e.g., flat market/bad data)
            if np.var(returns) < 1e-9:
                logger.warning(
                    "RegimeFilter: Statistical Floor Veto (Variance < 1e-9). fitting aborted."
                )
                return

            model = hmm.GaussianHMM(
                n_components=self.n_regimes,
                covariance_type="diag",
                n_iter=100,
                random_state=42,
                tol=1e-2,
            )
            model.fit(returns)
            self._model = model
            # Label regimes by mean return: highest = bull, lowest = bear
            means = [model.means_[i][0] for i in range(self.n_regimes)]
            sorted_idx = np.argsort(means)
            self._regime_labels = {
                sorted_idx[0]: "BEAR",
                sorted_idx[1]: "SIDEWAYS",
                sorted_idx[2]: "BULL",
            }
            logger.info(f"RegimeFilter fitted. Labels: {self._regime_labels}")
        except ImportError:
            logger.warning("hmmlearn not installed — RegimeFilter disabled. pip install hmmlearn")
        except Exception as e:
            logger.error(f"RegimeFilter fit error: {e}")

    def predict(self, prices: np.ndarray) -> SignalResult:
        """Predict current regime from recent prices."""
        if self._model is None:
            return SignalResult("regime", 0.0, 0.3, "NEUTRAL", {"regime": "UNKNOWN"})

        returns = np.diff(np.log(np.abs(prices) + 1e-10)).reshape(-1, 1)
        returns = np.where(np.isfinite(returns), returns, 0.0)
        try:
            states = self._model.predict(returns)
            current_state = states[-1]
            regime = self._regime_labels.get(current_state, "SIDEWAYS")

            # Compute regime probability for confidence
            log_prob, posteriors = self._model.score_samples(returns)
            confidence = float(posteriors[-1][current_state])

            score = {"BULL": 0.8, "SIDEWAYS": 0.0, "BEAR": -0.8}.get(regime, 0.0)
            return SignalResult(
                "regime", score, confidence, regime, {"regime": regime, "state": int(current_state)}
            )
        except Exception as e:
            logger.error(f"RegimeFilter predict error: {e}")
            return SignalResult("regime", 0.0, 0.2, "NEUTRAL")


class MultiFactorAlpha:
    """
    Combines momentum, mean-reversion, volume surge into a composite score.
    Theory: Fama-French factor models, used by every quant fund.
    Weights are learned during backtesting.
    """

    def __init__(self, weights: Optional[dict] = None):
        # Default global weights or regime-specific map
        self.weights = weights or {
            "momentum_1m": 0.30,
            "momentum_5d": 0.20,
            "mean_reversion": 0.20,
            "vol_regime": 0.15,
            "volume_surge": 0.15,
        }
        self._vol_kalman = None
        self._vol_P = 1.0

    def compute(
        self, prices: np.ndarray, volumes: np.ndarray, regime: str = "DEFAULT"
    ) -> SignalResult:
        if len(prices) < 25:
            return SignalResult("multi_factor", 0.0, 0.1, "NEUTRAL")

        try:
            returns = np.diff(np.log(prices + 1e-10))

            # We use meaningful intraday windows since true multi-day data isn't always in buffer.
            # 1. 'Intraday Mid-term' (60-bar / 1-hour window)
            lookback_mid = min(len(returns), 60)
            mom_mid = float(np.sum(returns[-lookback_mid:])) if lookback_mid > 0 else 0.0

            # 2. 'Intraday Short-term' (15-bar / 15-minute window)
            lookback_short = min(len(returns), 15)
            mom_short = float(np.sum(returns[-lookback_short:])) if lookback_short > 0 else 0.0

            # 3. Short-term mean reversion (z-score of last 10 returns)
            if len(returns) >= 10:
                mu, sigma = np.mean(returns[-10:]), np.std(returns[-10:]) + 1e-10
                mean_rev = -float((returns[-1] - mu) / sigma)
            else:
                mean_rev = 0.0

            # 4. Volatility regime: low vol = favorable for trend
            if len(returns) >= 30:
                vol_now = float(np.std(returns[-10:]))
                vol_base = float(np.std(returns[-30:]))
                vol_regime = -1.0 if vol_now > vol_base * 1.8 else 0.5
            else:
                vol_regime = 0.0

            # 5. Volume surge confirmation
            if len(volumes) >= 20 and volumes[-1] > 0:
                vol_surge = float(volumes[-1] / (np.mean(volumes[-20:]) + 1e-10)) - 1.0
                vol_surge = np.clip(vol_surge, -1.0, 1.0)
            else:
                vol_surge = 0.0

            # Scale factors into -1 to 1 range (Normalization)
            factors = {
                "momentum_1m": np.clip(
                    mom_mid * 80, -1, 1
                ),  # Key kept for trained_weights compatibility
                "momentum_5d": np.clip(
                    mom_short * 150, -1, 1
                ),  # Key kept for trained_weights compatibility
                "mean_reversion": np.clip(mean_rev * 0.5, -1, 1),
                "vol_regime": vol_regime,
                "volume_surge": float(np.clip(vol_surge, -1, 1)),
            }

            # SELECT WEIGHTS (Regime-Aware Selection)
            # If weights is a flat dict, use it. If nested, use regime key or 'DEFAULT'.
            w_map = self.weights
            if any(isinstance(v, dict) for v in self.weights.values()):
                w_map = self.weights.get(regime, self.weights.get("DEFAULT", self.weights))

            score = float(sum(w_map[k] * v for k, v in factors.items()))
            confidence = min(0.95, 0.5 + abs(score) * 0.5)

            return SignalResult(
                "multi_factor",
                score,
                confidence,
                "BUY" if score > 0.05 else "SELL" if score < -0.05 else "NEUTRAL",
                {
                    "factors": {k: round(v, 3) for k, v in factors.items()},
                    "regime_applied": regime if w_map != self.weights else "GLOBAL",
                },
            )
        except Exception as e:
            logger.error(f"MultiFactorAlpha error: {e}")
            return SignalResult("multi_factor", 0.0, 0.1, "NEUTRAL")


class KalmanEntryTimer:
    """
    Kalman filter estimates the 'true' price. Deviation from estimate = entry signal.
    Theory: Used by quantitative traders for optimal entry timing.
    """

    def __init__(self, process_noise: float = 1e-4, observation_noise: float = 1e-2):
        self.Q = process_noise  # process noise
        self.R = observation_noise  # observation noise
        self._states: dict[str, dict] = {}

    def _get_state(self, symbol: str) -> dict:
        if symbol not in self._states:
            self._states[symbol] = {"x": None, "P": 1.0, "last_price": 0.0}
        return self._states[symbol]

    def update(self, symbol: str, price: float) -> float:
        """Update Kalman state with new price. Returns estimated true price."""
        state = self._get_state(symbol)
        if state["x"] is None:
            state["x"] = price
            return price
        # Predict
        P_pred = state["P"] + self.Q
        # Update
        K = P_pred / (P_pred + self.R)
        state["x"] = state["x"] + K * (price - state["x"])
        state["P"] = (1 - K) * P_pred
        state["last_price"] = price
        return state["x"]

    def compute(self, symbol: str, prices: np.ndarray) -> SignalResult:
        """
        Incremental Kalman computation.
        Only runs the loop if it's a new symbol or history is missing.
        """
        if len(prices) < 10:
            return SignalResult("kalman_entry", 0.0, 0.2, "NEUTRAL")

        try:
            state = self._get_state(symbol)
            current_price = float(prices[-1])

            # Optimization: If the last seen price for this symbol is the previous bar,
            # just update with the NEW bar instead of re-running the entire array.
            if (
                state["x"] is not None
                and len(prices) >= 2
                and abs(prices[-2] - state["last_price"]) < 1e-8
            ):
                kalman_estimate = self.update(symbol, current_price)
            else:
                # Re-run full array (Initial or Gap detected)
                state["x"] = None
                state["P"] = 1.0
                kalman_estimate = 0.0
                for p in prices:
                    kalman_estimate = self.update(symbol, float(p))

            recent_std = float(np.std(prices[-20:])) if len(prices) >= 20 else 1.0
            deviation = (current_price - kalman_estimate) / (recent_std + 1e-10)

            score = float(np.clip(-deviation * 0.5, -1.0, 1.0))
            confidence = min(0.9, 0.4 + abs(deviation) * 0.2)

            return SignalResult(
                "kalman_entry",
                score,
                confidence,
                "BUY" if score > 0.05 else "SELL" if score < -0.05 else "NEUTRAL",
                {
                    "deviation": round(deviation, 3),
                    "kalman_price": round(kalman_estimate, 4),
                    "market_price": round(current_price, 4),
                },
            )
        except Exception as e:
            logger.error(f"KalmanEntryTimer error: {e}")
            return SignalResult("kalman_entry", 0.0, 0.2, "NEUTRAL")


class KellyPositionSizer:
    """
    Mathematically optimal position sizing using Kelly Criterion.
    Theory: Ed Thorp proved this is the optimal long-run growth strategy.
    Uses HALF-Kelly for safety (industry standard).
    """

    def compute(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        portfolio_value: float,
        max_fraction: float = 0.10,
    ) -> SignalResult:
        """
        Returns optimal position size in dollars.
        max_fraction: never risk more than this % of portfolio (default 10%)
        """
        try:
            if avg_loss <= 0 or win_rate <= 0 or win_rate >= 1:
                return SignalResult("kelly", 0.0, 0.5, "NEUTRAL", {"position_usd": 0, "kelly_f": 0})

            b = avg_win / avg_loss
            p, q = win_rate, 1.0 - win_rate

            if b <= 0:
                return SignalResult("kelly", 0.0, 0.5, "NEUTRAL", {"position_usd": 0, "kelly_f": 0})

            kelly_f = (b * p - q) / b

            # Half-Kelly for safety
            half_kelly = max(0.0, kelly_f * 0.5)
            # Cap at max_fraction
            safe_fraction = min(half_kelly, max_fraction)
            position_usd = safe_fraction * portfolio_value

            confidence = min(0.9, win_rate + 0.1)
            score = min(1.0, safe_fraction * 5)  # normalise to -1..1 range

            return SignalResult(
                "kelly",
                score,
                confidence,
                "BUY" if safe_fraction > 0 else "NEUTRAL",
                {
                    "kelly_f": round(kelly_f, 4),
                    "half_kelly_f": round(half_kelly, 4),
                    "safe_fraction": round(safe_fraction, 4),
                    "position_usd": round(position_usd, 2),
                },
            )
        except Exception as e:
            logger.error(f"KellyPositionSizer error: {e}")
            return SignalResult("kelly", 0.0, 0.3, "NEUTRAL", {"position_usd": 0})


class QuantConsensus:
    """
    Aggregates all quant signals into a final consensus vote.
    Auto-loads trained weights from src/trained_weights.json if available.
    """

    def __init__(self):
        # Try to load trained weights from Phase 1 training
        trained_weights = self._load_trained_weights()
        self.regime_filter = RegimeFilter()
        self.alpha_model = MultiFactorAlpha(weights=trained_weights)
        self.entry_timer = KalmanEntryTimer()
        self.position_sizer = KellyPositionSizer()
        self._fitted = False
        if trained_weights:
            logger.info("QuantConsensus: loaded trained weights from Phase 1")

    @staticmethod
    def _load_trained_weights() -> Optional[dict]:
        import json
        import os

        paths = [
            os.path.join(os.path.dirname(__file__), "trained_weights.json"),
            "src/trained_weights.json",
            "trained_weights.json",
        ]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p) as f:
                        data = json.load(f)

                    version = data.get("version", "UNKNOWN")
                    trained_at = data.get("trained_at", "UNKNOWN")
                    logger.info(
                        f"QuantConsensus: Sourcing weights from {p} (Version: {version}, Trained: {trained_at})"
                    )

                    return data.get("factor_weights")
                except Exception:
                    pass
        return None

    def fit(self, prices: np.ndarray) -> None:
        """Fit HMM regime filter. Must be called before live use."""
        self.regime_filter.fit(prices)
        self._fitted = True
        logger.info("QuantConsensus: all models fitted.")

    def evaluate(
        self,
        symbol: str,
        prices: np.ndarray,
        volumes: np.ndarray,
        win_rate: float = 0.5,
        avg_win: float = 1.0,
        avg_loss: float = 1.0,
        portfolio_value: float = STARTING_CAPITAL_CAD,
        regime_override: Optional[str] = None,
    ) -> dict:
        """
        Run all 4 signals and return aggregated consensus.
        Returns dict compatible with existing brain.consensus structure.
        """
        regime_signal = self.regime_filter.predict(prices)
        current_regime = regime_override or regime_signal.meta.get("regime", "UNKNOWN")

        alpha = self.alpha_model.compute(prices, volumes, regime=current_regime)
        entry = self.entry_timer.compute(symbol, prices)
        sizing = self.position_sizer.compute(win_rate, avg_win, avg_loss, portfolio_value)

        signals = [regime_signal, alpha, entry]
        buy_conf = sum(s.confidence for s in signals if s.vote == "BUY")
        sell_conf = sum(s.confidence for s in signals if s.vote == "SELL")
        total_conf = sum(s.confidence for s in signals) + 1e-10

        if buy_conf > sell_conf and buy_conf / total_conf > 0.45:
            bias, phase = "BULLISH", "BUY"
        elif sell_conf > buy_conf and sell_conf / total_conf > 0.45:
            bias, phase = "BEARISH", "SELL"
        else:
            bias, phase = "NEUTRAL", "HOLD"

        # Block trade if regime disagrees with alpha direction
        regime_veto = (phase == "BUY" and regime_signal.vote == "SELL") or (
            phase == "SELL" and regime_signal.vote == "BUY"
        )
        if regime_veto:
            phase = "HOLD"
            bias = "NEUTRAL"

        confidence = (buy_conf if phase == "BUY" else sell_conf) / total_conf

        return {
            "phase": phase,
            "bias": bias,
            "confidence": round(confidence, 4),
            "position_usd": sizing.meta.get("position_usd", 0),
            "kelly_fraction": sizing.meta.get("safe_fraction", 0),
            "regime": regime_signal.meta.get("regime", "UNKNOWN"),
            "regime_veto": int(regime_veto),
            "signals": {
                "regime": {
                    "score": regime_signal.score,
                    "vote": regime_signal.vote,
                    "conf": regime_signal.confidence,
                },
                "alpha": {
                    "score": alpha.score,
                    "vote": alpha.vote,
                    "conf": alpha.confidence,
                    "factors": alpha.meta.get("factors", {}),
                },
                "entry": {
                    "score": entry.score,
                    "vote": entry.vote,
                    "conf": entry.confidence,
                    "deviation": entry.meta.get("deviation", 0),
                },
                "sizing": sizing.meta,
            },
        }
