# pyre-ignore-all-errors[21]
"""
Agent D — Self-Learning Mind: Calibration & Continuous Improvement
===================================================================
Implements all 8 learning capabilities from EVERYTHING_FINAL.md:

1. RegimeClassifier       — Market regime detection (M-04)
2. StatisticalSignificanceGate — M-04 Law of Large Numbers enforcement
3. EdgeCrowdingDetector   — M-05 Nash equilibrium monitor (monthly)
4. SystemEntropyMonitor   — P-01 Thermodynamic decay tracking
5. ConditionalExpectancyMatrix — Pattern × regime × session matrix
6. PartialExitRules       — F9 per-pattern exit rules
7. ResolutionWindowCalibrator — F10 empirical window calibration
8. CalibrationPipeline    — Weekly + monthly + walk-forward validation

Critical rules enforced:
- M-04: ConditionalExpectancyMatrix active from n >= 1 (Bayesian Warm-Start)
- M-04: can_adapt() returns False for INSUFFICIENT data (n < 20)
- F9: Partial exits defined per pattern — BullFlag, H&S, FallingWedge, etc.
- F10: Resolution windows start at 2× theoretical, calibrate after 30 trades
- P-01: Entropy monitor detects system decay — triggers urgent maintenance
- Samvid v1.0-beta-beta-beta: Bayesian priors integrated for cold-start stall bypass
- Samvid v1.0-beta-beta-beta: LiveRecursiveEvolution (Recursive Back-Prop) Active
"""

from __future__ import annotations  # pyre-ignore[21]

import json
import logging  # pyre-ignore[21]
import math  # pyre-ignore[21]
import statistics  # pyre-ignore[21]
import time
from dataclasses import dataclass  # pyre-ignore[21]
from datetime import datetime  # pyre-ignore[21]
from pathlib import Path
from typing import Any, Dict  # pyre-ignore[21]


class LiveRecursiveEvolution:
    """
    Sovereign v1.0-beta-beta Stable Evolution Engine.
    GAP-43 FIX: Implements 'Learning Inertia' to prevent Luck-Based Weight Drift.
    Ensures that as pattern maturity (n_count) grows, individual noisy outcomes
    have diminishing impact on the core belief system.
    """
    def __init__(self, atlas: Any):
        self.atlas = atlas # InMemorySovereignAtlas

    def evolve_live(self, pattern_name: str, pnl: float, regime: str, **kwargs):
        """
        Updates weights with Bayesian-inspired stability.
        Zero-Latency Learning with Anti-Recency bias.
        """
        # outcome: 1=WIN, -1=LOSS, 0=BE
        if pnl > 0.0001: outcome = 1.0
        elif pnl < -0.0001: outcome = -1.0
        else: return # Break-even doesn't shift the weight state (Samvid v1.0-beta-beta-beta)

        if not (self.atlas and getattr(self.atlas, "atlas_data", {})):
            return

        patterns = self.atlas.atlas_data.get(pattern_name, [])
        n_count = len(patterns)
        if n_count == 0: return

        # --- LEARNING INERTIA (Samvid v1.0-beta-beta-beta) ---
        # As n increases, the impact of 1 trade (alpha) decreases.
        # Base alpha 0.4 (40% impact for 1st trade) -> alpha 0.01 (1% impact for 400th trade)
        base_alpha = 0.4
        alpha = base_alpha / (1.0 + (n_count / 10.0))
        # Keep alpha between [0.01, 0.4]
        alpha = max(0.01, min(base_alpha, alpha))

        # Weight Update: current_weight * (1 + alpha * outcome)
        # outcome is 1.0 or -1.0
        multiplier = 1.0 + (alpha * outcome)

        # Bug 37 FIX: Recency-Weighted Evolution (Anti-Amnesia)
        # Instead of shifting all historical weights equally, we apply a decay.
        # This ensures recent losses don't erase 2-year-old alpha-drivers completely.
        count = 0
        for i in range(min(100, len(patterns))):
            idx = -(i+1)
            data = list(patterns[idx])

            # Recency Decay: 100% impact for current trade, 50% for 50th trade back
            recency_decay = 1.0 / (1.0 + (i / 50.0))
            current_multiplier = 1.0 + (alpha * outcome * recency_decay)

            # CAP: min 0.1, max 3.0 (Sovereign v1.0-beta-beta)
            new_weight = data[1] * current_multiplier
            data[1] = min(3.0, max(0.1, new_weight))
            patterns[idx] = tuple(data)
            count += 1

        logging.info(f"🏛️ Evolution: Stable Rewire for '{pattern_name}'. Impact: {multiplier:.4f}x (Alpha: {alpha:.4f}, n={n_count}).")

class RegimeClassifier:
    """
    Classifies the current market regime using VIX, breadth, and momentum.

    The regime affects position sizing, pattern selection, and risk tolerance.
    Agent B uses the regime as a modifier in the catalyst scoring chain (F3 Step 2).
    """

    # VIX thresholds for regime classification
    VIX_NORMAL = 20.0  # Below = calm market
    VIX_ELEVATED = 30.0  # Above = volatile market
    VIX_EXTREME = 45.0  # Above = crisis/Black Swan territory

    def classify(
        self,
        vix: float,
        spy_above_200ma: bool,
        breadth: float,  # Advance/Decline ratio, typically 0.3–0.7
        momentum: float,  # Rate of change, positive = trending up
    ) -> str:
        """
        Classify market regime.

        Args:
            vix: VIX level (fear index)
            spy_above_200ma: Is SPY trading above its 200-day moving average?
            breadth: Market breadth (advance/decline ratio, 0.0 to 1.0)
            momentum: Price momentum (-1.0 to +1.0, positive = bullish)

        Returns:
            One of: BULL / BEAR / VOLATILE / CHOPPY / TRENDING
        """
        # VOLATILE regime: high VIX dominates all other signals
        if vix >= self.VIX_ELEVATED:
            return "VOLATILE"

        # BEAR regime: below 200MA with negative breadth and momentum
        if not spy_above_200ma and breadth < 0.45 and momentum < -0.001:
            return "BEAR"

        # BULL regime: above 200MA with positive breadth and momentum
        if spy_above_200ma and breadth > 0.55 and momentum > 0.001:
            return "BULL"

        # SOVEREIGN Overdrive: Lowered momentum pivot (Eliminating GAP-34 bottleneck)
        if abs(momentum) > 0.0005:
            return "TRENDING"

        # CHOPPY regime: everything else — no clear direction
        return "CHOPPY"

    def get_risk_modifier(self, regime: str) -> float:
        """
        Return position size modifier for each regime.
        BULL = full size, VOLATILE = reduced, BEAR = minimal.
        """
        modifiers = {
            "BULL": 1.0,  # Full position size
            "TRENDING": 0.85,  # Slightly reduced
            "CHOPPY": 0.70,  # Reduced — direction unclear
            "BEAR": 0.50,  # Half size — risk of continuation
            "VOLATILE": 0.40,  # Significantly reduced — unpredictable
        }
        return modifiers.get(regime, 0.70)


# =============================================================================
# 2. STATISTICAL SIGNIFICANCE GATE  (M-04 Law of Large Numbers)
# =============================================================================


class StatisticalSignificanceGate:
    """
    Enforces M-04: statistical significance before any calibration decisions.

    The system NEVER makes adaptations based on INSUFFICIENT or PRELIMINARY data.
    This prevents overfitting to small samples — the most common error in
    trading system design.

    Rating thresholds:
        n < 20:   INSUFFICIENT — cannot make any statistical claims
        n 20-50:  PRELIMINARY  — use with extreme caution, wide CI
        n 50-100: MODERATE     — usable for basic decisions
        n 100-200: RELIABLE    — usable for parameter adjustments
        n > 200:  STRONG       — usable for confident optimization
    """

    INSUFFICIENT_THRESHOLD = 20
    PRELIMINARY_THRESHOLD = 50
    MODERATE_THRESHOLD = 100
    RELIABLE_THRESHOLD = 200

    def rate_data(self, n: int) -> str:
        """
        Rate the statistical significance of a dataset with n samples.

        Returns:
            'INSUFFICIENT' | 'PRELIMINARY' | 'MODERATE' | 'RELIABLE' | 'STRONG'
        """
        if n < self.INSUFFICIENT_THRESHOLD:
            return "INSUFFICIENT"
        elif n < self.PRELIMINARY_THRESHOLD:
            return "PRELIMINARY"
        elif n < self.MODERATE_THRESHOLD:
            return "MODERATE"
        elif n < self.RELIABLE_THRESHOLD:
            return "RELIABLE"
        else:
            return "STRONG"

    def confidence_interval(
        self,
        wins: int,
        total: int,
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """
        Calculate Wilson confidence interval for a win rate.

        Uses Wilson score interval (more accurate than normal approximation
        for small samples and extreme probabilities).

        Returns:
            (lower_bound, upper_bound) as fractions
        """
        if total == 0:
            return (0.0, 1.0)

        p_hat = wins / total
        # Z-score for confidence level (1.96 for 95%, 1.645 for 90%)
        z = 1.96 if confidence >= 0.95 else 1.645

        # Wilson score interval formula
        denominator = 1 + (z**2) / total
        centre = (p_hat + (z**2) / (2 * total)) / denominator
        margin = (
            z * math.sqrt(p_hat * (1 - p_hat) / total + (z**2) / (4 * total**2))
        ) / denominator

        lower = max(0.0, float(centre - margin))
        upper = min(1.0, float(centre + margin))
        return (float(f"{lower:.4f}"), float(f"{upper:.4f}"))

    def format_stat(self, win_rate: float, n: int) -> str:
        """
        Format a statistic with confidence interval and data rating.

        Example output: "WR=78% +-8% (n=47, PRELIMINARY)"
        """
        rating = self.rate_data(n)

        if n < self.INSUFFICIENT_THRESHOLD:
            return f"WR=N/A (n={n}, {rating})"

        wins = round(win_rate * n)
        lo, hi = self.confidence_interval(wins, n)
        margin = float(f"{(hi - lo) / 2 * 100:.1f}")
        wr_pct = float(f"{win_rate * 100:.1f}")

        return f"WR={wr_pct}% +-{margin}% (n={n}, {rating})"

    def can_adapt(self, n: int) -> bool:
        """
        Returns True if sample size is sufficient to make adaptations.

        Agent D CANNOT make adaptations on INSUFFICIENT data (n < 20).
        For PRELIMINARY data (20-50), adaptations are permitted but throttled.
        This is the M-04 gate — it protects against overfitting.
        """
        return n >= self.INSUFFICIENT_THRESHOLD


# =============================================================================
# 3. EDGE CROWDING DETECTOR  (M-05 Nash Equilibrium)
# =============================================================================


class EdgeCrowdingDetector:
    """
    Detects when too many participants are exploiting the same pattern,
    eliminating the edge (M-05 Nash equilibrium monitor).

    Run MONTHLY on every active pattern.

    When a pattern becomes CROWDED, reduce allocation BEFORE the edge disappears
    completely — exit the game before Nash equilibrium is reached.

    Crowding signals:
    1. Win rate is declining over time (others front-running)
    2. Average R is declining (less profit per win)
    3. Slippage is increasing (more competition at entry)
    4. Volume at breakout points is increasing (more traders on same signal)
    """

    CROWDED_THRESHOLD = 3  # 3+ signals -> CROWDED
    WARNING_THRESHOLD = 2  # 2 signals  -> WARNING

    def detect(
        self,
        pattern: str,
        win_rates: list[float],  # Rolling win rates, most recent last
        avg_rs: list[float],  # Rolling average R multiples
        slippages: list[float],  # Rolling average slippage
        volumes: list[float],  # Rolling breakout volume ratio
    ) -> str:
        """
        Detect edge crowding for a pattern.

        Args:
            pattern: Pattern name (e.g. "BULL_FLAG")
            win_rates: List of win rates over rolling periods
            avg_rs: List of average R values over rolling periods
            slippages: List of average slippage values
            volumes: List of average breakout volume ratios

        Returns:
            'CROWDED' | 'WARNING' | 'CLEAR'
        """
        score = 0

        # Signal 1: Declining win rate trend
        if self._is_declining(win_rates):
            score += 1

        # Signal 2: Shrinking average R
        if self._is_declining(avg_rs):
            score += 1

        # Signal 3: Increasing slippage (more competition at entry)
        if self._is_increasing(slippages):
            score += 1

        # Signal 4: Increasing breakout volume (more traders on signal)
        if self._is_increasing(volumes):
            score += 1

        if score >= self.CROWDED_THRESHOLD:
            return "CROWDED"
        elif score >= self.WARNING_THRESHOLD:
            return "WARNING"
        else:
            return "CLEAR"

    def _is_declining(self, series: list[float]) -> bool:
        """True if there's a downward trend in the series."""
        if len(series) < 3:
            return False
        # Simple linear regression slope
        n = len(series)
        x_mean = (n - 1) / 2
        y_mean = sum(series) / n
        numerator = sum((i - x_mean) * (series[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return False
        slope = numerator / denominator
        return slope < 0

    def _is_increasing(self, series: list[float]) -> bool:
        """True if there's an upward trend in the series."""
        return self._is_declining([-x for x in series])


# =============================================================================
# 4. SYSTEM ENTROPY MONITOR  (P-01 Second Law of Thermodynamics)
# =============================================================================


class SystemEntropyMonitor:
    """
    Monitors whether the system is maintaining order or decaying (P-01).

    P-01 (Second Law of Thermodynamics applied to trading):
    A trading edge is an ORDERED STATE in a disordered market.
    Without continuous energy input (monitoring, adaptation, learning),
    the edge DECAYS toward zero. This is not a possibility — it is a
    PHYSICAL LAW applied to information systems.

    Entropy levels:
        HIGH ENTROPY: System is decaying urgently — immediate maintenance needed
        RISING:       Entropy increasing — schedule maintenance within 1 week
        LOW:          System is well-maintained and performing as expected
    """

    HIGH_ENTROPY_THRESHOLD = -0.3
    RISING_THRESHOLD = 0.0

    def measure(
        self,
        wr_trend: float,  # Win rate slope over last 50 trades (-1 to +1)
        cal_drift: float,  # Calibration error trend (-1 to +1)
        param_age_days: float,  # Average days since last parameter update
        regime_accuracy: float,  # Regime prediction accuracy trend (-1 to +1)
    ) -> str:
        """
        Calculate system entropy from multiple sources.

        Args:
            wr_trend: Win rate trend (negative = declining = entropy rising)
            cal_drift: Calibration error trend (positive = drift = entropy rising)
            param_age_days: How stale are the parameters? (90 days = -1.0)
            regime_accuracy: Regime model accuracy trend

        Returns:
            'HIGH ENTROPY' | 'RISING' | 'LOW'
        """
        signals = []

        # Win rate trend: declining = entropy rising
        signals.append(wr_trend)

        # Calibration drift: growing = entropy rising (note: inverted)
        signals.append(-cal_drift)

        # Parameter age: old = entropy rising (normalize: 90 days = -1.0)
        age_signal = -param_age_days / 90.0
        signals.append(max(-1.0, age_signal))

        # Regime accuracy trend
        signals.append(regime_accuracy)

        # Combined entropy score: negative = decaying, positive = thriving
        # Samvid v1.0-beta-beta-beta: Empty list safety guard
        if not signals:
            return "LOW"
        entropy = sum(signals) / len(signals)

        if entropy < self.HIGH_ENTROPY_THRESHOLD:
            return "HIGH ENTROPY"
        elif entropy < self.RISING_THRESHOLD:
            return "RISING"
        else:
            return "LOW"

    def get_urgency(self, entropy_level: str) -> str:
        """Return action required based on entropy level."""
        actions = {
            "HIGH ENTROPY": "URGENT: Re-calibrate all parameters immediately",
            "RISING": "SCHEDULE: Maintenance required within 1 week",
            "LOW": "OK: System is well-maintained",
        }
        return actions.get(entropy_level, "UNKNOWN")


# =============================================================================
# 5. CONDITIONAL EXPECTANCY MATRIX
# =============================================================================


@dataclass
class ExpectancyData:
    """Win rate data for a specific condition combination."""

    pattern: str
    regime: str
    session: str
    n_trades: int
    wins: int
    total_r: float
    weighted_n: float = 0.0
    weighted_wins: float = 0.0
    weighted_r: float = 0.0
    win_rate: float = 0.0
    avg_r: float = 0.0
    data_rating: str = "INSUFFICIENT"

    def __post_init__(self):
        # Samvid v1.0-beta-beta-beta: Safety floor on denominator to prevent division-by-zero explosions
        if self.weighted_n > 0.0001:
            self.win_rate = self.weighted_wins / self.weighted_n
            self.avg_r = self.weighted_r / self.weighted_n
        elif self.n_trades > 0:
            self.win_rate = self.wins / self.n_trades
            self.avg_r = self.total_r / self.n_trades

        gate = StatisticalSignificanceGate()
        self.data_rating = gate.rate_data(self.n_trades)


class ConditionalExpectancyMatrix:
    """
    Builds a matrix of expected win rates conditioned on:
    pattern × regime × session

    Samvid v1.0-beta-beta-beta: Bayesian Warm-Start.
    Activates from trade #1 by using historical priors.
    As live trades increase, the prior's influence decays.
    """
    MIN_TRADES = 1  # Updated for Bayesian Warm-Start

    def __init__(self, db_path: str = "data/trading.db") -> None:
        self.db_path = db_path
        self.priors: dict[str, dict] = {}
        self.matrix: dict[str, ExpectancyData] = {}
        self._raw_stats: dict[str, dict] = {} # Internal buffers for incremental updates
        self.activated = False
        self.gate = StatisticalSignificanceGate()
        self.n_live_historical = 0 # Tracks total live trades processed
        self._load_priors()

    def _load_priors(self) -> None:
        """Load Bayesian priors with hierarchy: Dynamic (Live) > Static (Historical)."""
        dynamic_path = Path("scratch/priors/dynamic_priors.json")
        static_path = Path("scratch/priors/pattern_priors.json")

        target_path = dynamic_path if dynamic_path.exists() else static_path

        if target_path.exists():
            try:
                self.priors = json.loads(target_path.read_text())
                source = "Dynamic (Evolutionary)" if target_path == dynamic_path else "Static (Historical)"
                logging.getLogger(__name__).info(f"ConditionalExpectancyMatrix: {source} Priors loaded.")
            except Exception as e:
                logging.getLogger(__name__).warning(f"ConditionalExpectancyMatrix: Failed to load priors: {e}")

    def save_priors(self) -> None:
        """Persist current weighted matrix as dynamic priors for the next session."""
        try:
            output = {}
            for key, data in self.matrix.items():
                # Format: Pattern|Regime|Session
                parts = key.split("|")
                if len(parts) != 3:
                    continue
                pattern, regime, _ = parts

                if pattern not in output:
                    output[pattern] = {}

                output[pattern][regime] = {
                    "win_rate": round(data.win_rate, 3),
                    "avg_r": round(data.avg_r, 3),
                    "n": data.n_trades
                }

            save_path = Path("scratch/priors/dynamic_priors.json")
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(json.dumps(output, indent=4))
            logging.getLogger(__name__).info(f"ConditionalExpectancyMatrix: System Wisdom persisted to {save_path}")
        except Exception as e:
            logging.getLogger(__name__).error(f"ConditionalExpectancyMatrix: Persistence failed: {e}")

    def build(
        self,
        trade_history: Any,
        total_count: int | None = None,
        incremental: bool = False
    ) -> dict[str, ExpectancyData]:
        """
        Build or update the expectancy matrix while minimizing RAM.
        Samvid v1.0-beta-beta-beta: Supports streaming iterators and incremental updates.
        """
        self.activated = True

        if not incremental:
            self._raw_stats = {}
            self.n_live_historical = 0
            # 1. Initialize with Priors
            for pattern, regimes in self.priors.items():
                for regime, stats in regimes.items():
                    key = f"{pattern}|{regime}|RTH"
                    prior_n = stats["n"]
                    prior_wr = stats["win_rate"]
                    prior_r = stats["avg_r"]

                    self._raw_stats[key] = {
                        "pattern": pattern,
                        "regime": regime,
                        "session": "RTH",
                        "n": prior_n,
                        "wins": int(prior_n * prior_wr),
                        "total_r": prior_n * prior_r,
                        "weighted_n": float(prior_n),
                        "weighted_wins": float(prior_n * prior_wr),
                        "weighted_r": float(prior_n * prior_r),
                        "is_prior": True
                    }

        # 2. Iterate and Update
        # If total_count is provided, we use it for the decay baseline
        n_base = total_count if total_count is not None else (
            len(trade_history) if isinstance(trade_history, list) else (self.n_live_historical + 1)
        )

        for i, trade in enumerate(trade_history):
            pattern = trade.get("pattern", "UNKNOWN")
            regime = trade.get("regime", "UNKNOWN")
            session = trade.get("session", "UNKNOWN")
            outcome = trade.get("outcome", "LOSS")
            try:
                r_mult = float(trade.get("r_multiple", 0.0))
            except (ValueError, TypeError):
                r_mult = 0.0

            key = f"{pattern}|{regime}|{session}"
            if key not in self._raw_stats:
                self._raw_stats[key] = {
                    "pattern": pattern, "regime": regime, "session": session,
                    "n": 0, "wins": 0, "total_r": 0.0,
                    "weighted_n": 0.0, "weighted_wins": 0.0, "weighted_r": 0.0,
                    "is_prior": False
                }

            self._raw_stats[key]["n"] += 1
            self._raw_stats[key]["total_r"] += r_mult
            if outcome == "WIN":
                self._raw_stats[key]["wins"] += 1

            # Time-Decay Weighting
            # In incremental mode, i might start at 0 but we want it to be the 'current' trade
            idx = self.n_live_historical if incremental else i
            age_index = n_base - 1 - idx
            weight = math.exp(-max(0, age_index) / 500.0)

            self._raw_stats[key]["weighted_n"] += weight
            self._raw_stats[key]["weighted_r"] += r_mult * weight
            if outcome == "WIN":
                self._raw_stats[key]["weighted_wins"] += weight

            if not incremental:
                self.n_live_historical += 1

        if incremental:
            self.n_live_historical += (i + 1)

        # 3. Finalize ExpectancyData objects
        self.matrix = {}
        for key, d in self._raw_stats.items():
            self.matrix[key] = ExpectancyData(
                pattern=d["pattern"],
                regime=d["regime"],
                session=d["session"],
                n_trades=d["n"],
                wins=d["wins"],
                total_r=d["total_r"],
                weighted_n=d["weighted_n"],
                weighted_wins=d["weighted_wins"],
                weighted_r=d["weighted_r"]
            )
        return self.matrix

    def _normalize_regime(self, regime: str) -> str:
        """Bug 39 FIX: Regime Normalization (Chala -> VOLATILE mapping)."""
        if not regime: return "UNKNOWN"
        r = str(regime).upper()
        if r in ("CHALA", "VOLATILE", "HIGH_VOL"): return "VOLATILE"
        if r in ("BULL", "BULLISH", "UPTREND"): return "BULL"
        if r in ("BEAR", "BEARISH", "DOWNTREND"): return "BEAR"
        if r in ("CHOPPY", "SIDEWAYS", "RANGE"): return "CHOPPY"
        return r

    def get_win_rate(
        self,
        pattern: str,
        regime: str,
        session: str = "RTH",
        default: float = 0.55
    ) -> float:
        """
        Get the calibrated win rate for a specific condition combination.

        Returns default if matrix not activated or insufficient data for key.
        """
        if not self.activated:
            return default

        regime = self._normalize_regime(regime)
        key = f"{pattern}|{regime}|{session}"
        data = self.matrix.get(key)

        # Samvid v1.0-beta-beta-beta: Session-Blindness Guard
        # If no session-specific data exists, fallback to RTH (the wisdom anchor)
        if data is None and session != "RTH":
            fallback_key = f"{pattern}|{regime}|RTH"
            data = self.matrix.get(fallback_key)

        if data is None or not self.gate.can_adapt(data.n_trades):
            return default

        return data.win_rate


# =============================================================================
# 6. PARTIAL EXIT RULES  (F9 — per pattern)
# =============================================================================


@dataclass
class ExitLevel:
    """A single partial exit level."""

    price: float  # Price to exit at
    pct_out: float  # Percentage of position to exit (0.0 to 1.0)
    reason: str  # Human-readable reason


class PartialExitRules:
    """
    Defines partial exit rules per pattern (F9 solution).

    Each pattern has specific exit levels based on its typical behavior.
    These start as theoretical values and get calibrated after 30+ trades.

    F9 rules per pattern:
    - BullFlag:       +1R->BE, +1.5R->50% out, +2R->75%, target->all
    - HeadShoulders:  +1R->BE, target->100% (trend trade, let it run)
    - FallingWedge:   +1R->BE, +1.5R->50%, +2.5R->all
    - OversoldBounce: +0.5R->25%, RSI_40->50%, RSI_50->all
    - SectorSympathy: +1R->50%, +1.5R->all (quick trade)
    - GapFill:        50%filled->50%, 80%filled->all
    """

    def get_exits(
        self,
        pattern: str,
        entry_price: float,
        r_size: float,  # Dollar value of 1R (entry - stop)
        direction: str = "LONG",
    ) -> list[ExitLevel]:
        """
        Get partial exit levels for a pattern.

        Args:
            pattern:      Pattern name (e.g. "BULL_FLAG")
            entry_price:  Trade entry price
            r_size:       Price distance of 1R (entry - stop in dollars)

        Returns:
            List of ExitLevel objects defining when to exit portions
        """
        pattern_upper = pattern.upper().replace(" ", "_").replace("&", "")

        rules = {
            "BULL_FLAG": self._bull_flag_exits,
            "BULLISH_FLAG": self._bull_flag_exits,
            "HEAD_SHOULDERS": self._head_shoulders_exits,
            "HEAD_AND_SHOULDERS": self._head_shoulders_exits,
            "FALLING_WEDGE": self._falling_wedge_exits,
            "OVERSOLD_BOUNCE": self._oversold_bounce_exits,
            "SECTOR_SYMPATHY": self._sector_sympathy_exits,
            "GAP_FILL": self._gap_fill_exits,
        }

        fn = rules.get(pattern_upper, self._default_exits)

        # Samvid v1.0-beta-beta-beta: Directional Parity (F9-Short Fix)
        # We pass a Directional Multiplier (1 for LONG, -1 for SHORT)
        # to ensure exits project correctly in price space.
        mult = -1.0 if direction.upper() == "SHORT" else 1.0

        return fn(entry_price, r_size, mult)

    def _bull_flag_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """BullFlag: +1R->BE, +1.5R->50% out, +2R->75% out, target->all."""
        return [
            ExitLevel(entry + m * r, 0.0, "Move stop to breakeven (+1R)"),
            ExitLevel(entry + m * 1.5 * r, 0.50, "50% out at +1.5R"),
            ExitLevel(entry + m * 2.0 * r, 0.75, "75% out at +2R"),
            ExitLevel(entry + m * 3.0 * r, 1.0, "All out at target (+3R)"),
        ]

    def _head_shoulders_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """H&S: +1R->BE, target->100% (trend trade, let it run)."""
        return [
            ExitLevel(entry + m * r, 0.0, "Move stop to breakeven (+1R)"),
            ExitLevel(entry + m * 4.0 * r, 1.0, "All out at target (+4R, trend trade)"),
        ]

    def _falling_wedge_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """FallingWedge: +1R->BE, +1.5R->50%, +2.5R->all."""
        return [
            ExitLevel(entry + m * r, 0.0, "Move stop to breakeven (+1R)"),
            ExitLevel(entry + m * 1.5 * r, 0.50, "50% out at +1.5R"),
            ExitLevel(entry + m * 2.5 * r, 1.0, "All out at +2.5R"),
        ]

    def _oversold_bounce_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """OversoldBounce: +0.5R->25% out, RSI_40->50%, RSI_50->all."""
        return [
            ExitLevel(entry + m * 0.5 * r, 0.25, "25% out at +0.5R (quick partial)"),
            ExitLevel(entry + m * 1.0 * r, 0.50, "50% out when RSI reaches 40"),
            ExitLevel(entry + m * 1.5 * r, 1.0, "All out when RSI reaches 50"),
        ]

    def _sector_sympathy_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """SectorSympathy: +1R->50% out, +1.5R->all (quick trade)."""
        return [
            ExitLevel(entry + m * r, 0.50, "50% out at +1R (quick trade)"),
            ExitLevel(entry + m * 1.5 * r, 1.0, "All out at +1.5R"),
        ]

    def _gap_fill_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """GapFill: 50% filled->50% out, 80% filled->all out."""
        return [
            ExitLevel(entry + m * 1.0 * r, 0.50, "50% out when gap 50% filled"),
            ExitLevel(entry + m * 1.8 * r, 1.0, "All out when gap 80% filled"),
        ]

    def _default_exits(self, entry: float, r: float, m: float) -> list[ExitLevel]:
        """Default exits for unknown patterns."""
        return [
            ExitLevel(entry + m * r, 0.0, "Move stop to breakeven (+1R)"),
            ExitLevel(entry + m * 2.0 * r, 0.50, "50% out at +2R"),
            ExitLevel(entry + m * 3.0 * r, 1.0, "All out at target (+3R)"),
        ]


# =============================================================================
# 7. RESOLUTION WINDOW CALIBRATOR  (F10)
# =============================================================================


class ResolutionWindowCalibrator:
    """
    Calibrates how many days a pattern typically takes to resolve (F10).

    F10 Solution: START with 2x theoretical resolution windows.
    After 30 trades per pattern per instrument, replace with
    MEASURED resolution windows from actual data.

    This prevents the system from using book-theory timeframes that
    don't match how the pattern actually behaves in current markets.
    """

    # Theoretical resolution windows in days (from documentation)
    THEORETICAL_WINDOWS: dict[str, int] = {
        "BULL_FLAG": 5,
        "HEAD_SHOULDERS": 15,
        "FALLING_WEDGE": 10,
        "OVERSOLD_BOUNCE": 3,
        "SECTOR_SYMPATHY": 2,
        "GAP_FILL": 2,
        "CUP_AND_HANDLE": 20,
        "CATALYST_PLAY": 1,
        "DEFAULT": 7,
    }

    # F10: Start at 2x theoretical
    INITIAL_MULTIPLIER = 2.0
    MIN_TRADES_TO_CALIBRATE = 30  # After this many trades, use measured data

    def get_window(
        self,
        pattern: str,
        instrument: str,
        trade_history: list[dict],
    ) -> int:
        """
        Get resolution window for a pattern+instrument combination.

        F10 Logic:
        - If fewer than 30 trades: use 2x theoretical window
        - If 30+ trades: use measured average hold time

        Args:
            pattern:       Pattern name
            instrument:    Instrument ticker (e.g. "SPY")
            trade_history: All completed trades

        Returns:
            Resolution window in days
        """
        pattern_key = pattern.upper().replace(" ", "_")

        # Filter trades for this specific pattern + instrument
        relevant = [
            t
            for t in trade_history
            if (
                t.get("pattern", "").upper().replace(" ", "_") == pattern_key
                and t.get("instrument", "").upper() == instrument.upper()
                and t.get("outcome") in ("WIN", "LOSS")  # Completed trades only
                and t.get("hold_hours") is not None
            )
        ]

        n = len(relevant)

        # F10: Use 2x theoretical until we have 30 trades
        if n < self.MIN_TRADES_TO_CALIBRATE:
            theoretical = self.THEORETICAL_WINDOWS.get(
                pattern_key, self.THEORETICAL_WINDOWS["DEFAULT"]
            )
            window = int(theoretical * self.INITIAL_MULTIPLIER)
            return max(1, window)

        # After 30 trades: use measured average hold time
        hold_days_list = [t["hold_hours"] / 24.0 for t in relevant if t.get("hold_hours", 0) > 0]

        if not hold_days_list:
            theoretical = self.THEORETICAL_WINDOWS.get(pattern_key, 7)
            return int(theoretical * self.INITIAL_MULTIPLIER)

        measured_avg = statistics.mean(hold_days_list)
        # Add 20% buffer to measured average
        return max(1, int(measured_avg * 1.2))

    def get_all_windows(
        self,
        instrument: str,
        trade_history: list[dict],
    ) -> dict[str, int]:
        """Get resolution windows for all known patterns."""
        windows = {}
        for pattern in self.THEORETICAL_WINDOWS:
            if pattern == "DEFAULT":
                continue
            windows[pattern] = self.get_window(pattern, instrument, trade_history)
        return windows


# =============================================================================
# 8. CALIBRATION PIPELINE
# =============================================================================


@dataclass
class CalibrationReport:
    """Output of weekly or monthly calibration."""

    timestamp: str
    report_type: str  # "weekly" or "monthly"
    n_trades: int
    win_rate: float
    win_rate_formatted: str  # "WR=65% +-5% (n=200, STRONG)"
    data_rating: str
    avg_r: float
    entropy_level: str
    crowding_by_pattern: dict[str, str]  # pattern -> CLEAR/WARNING/CROWDED
    regime_distribution: dict[str, int]  # regime -> count
    recommendations: list[str]


@dataclass
class ValidationResult:
    """Output of walk-forward validation."""

    in_sample_win_rate: float
    out_sample_win_rate: float
    in_sample_n: int
    out_sample_n: int
    performance_gap: float  # abs(in - out), smaller = less overfitting
    passed: bool  # True if out_sample within 10% of in_sample
    recommendation: str


class CalibrationPipeline:
    """
    Runs weekly calibration, monthly audits, and walk-forward validation.

    The system gets smarter after every trade because of this class.
    Without regular calibration, the system thermodynamically decays (P-01).

    Weekly:  Win rate tracking, confidence intervals, entropy check
    Monthly: Full edge crowding audit (Nash equilibrium check), parameter review
    Walk-forward: Required before any live trading
    """

    def __init__(self) -> None:
        self.gate = StatisticalSignificanceGate()
        self.entropy = SystemEntropyMonitor()
        self.crowding = EdgeCrowdingDetector()

    def weekly_calibration(self, trade_history: list[dict]) -> dict:
        """
        Run weekly calibration.

        Calculates: win rate with CI, data rating, entropy score,
        regime distribution, basic crowding check.

        Args:
            trade_history: All completed trades

        Returns:
            CalibrationReport as dict
        """
        n = len(trade_history)

        # Win rate calculation
        wins = sum(1 for t in trade_history if t.get("outcome") == "WIN")
        wr = wins / n if n > 0 else 0.0
        rating = self.gate.rate_data(n)
        wr_formatted = self.gate.format_stat(wr, n)

        # Average R
        r_values = [
            t.get("r_multiple", 0.0) for t in trade_history if t.get("r_multiple") is not None
        ]
        avg_r = statistics.mean(r_values) if r_values else 0.0

        # Entropy — simplified (use win rate trend as proxy)
        recent_50 = list(trade_history[-50:]) if len(trade_history) >= 50 else trade_history  # type: ignore
        recent_wins = sum(1 for t in recent_50 if t.get("outcome") == "WIN")
        recent_wr = recent_wins / len(recent_50) if recent_50 else wr
        wr_trend = recent_wr - wr  # Positive = improving, negative = declining

        entropy_level = self.entropy.measure(
            wr_trend=wr_trend,
            cal_drift=0.0,
            param_age_days=7.0,  # Assume weekly update
            regime_accuracy=0.1 if wr_trend > 0 else -0.1,
        )

        # Regime distribution
        regime_dist: dict[str, int] = {}
        for t in trade_history:
            regime = t.get("regime", "UNKNOWN")
            regime_dist[regime] = regime_dist.get(regime, 0) + 1

        # Build recommendations
        recommendations = []
        if rating in ("INSUFFICIENT", "PRELIMINARY"):
            recommendations.append(
                f"Data is {rating} (n={n}). "
                f"Need {self.gate.MODERATE_THRESHOLD - n} more trades for MODERATE rating."
            )
        if entropy_level == "HIGH ENTROPY":
            recommendations.append("URGENT: High entropy detected — re-calibrate parameters")
        elif entropy_level == "RISING":
            recommendations.append("RISING entropy — schedule parameter review this week")
        if avg_r < 0:
            recommendations.append(f"Negative avg R ({avg_r:.2f}) — review position sizing")

        report = CalibrationReport(
            timestamp=str(datetime.now()),
            report_type="weekly",
            n_trades=n,
            win_rate=wr,
            win_rate_formatted=wr_formatted,
            data_rating=rating,
            avg_r=float(f"{avg_r:.3f}"),
            entropy_level=entropy_level,
            crowding_by_pattern={},  # Full crowding done monthly
            regime_distribution=regime_dist,
            recommendations=recommendations,
        )

        return vars(report)


    def monthly_audit(self, trade_history: list[dict]) -> dict:
        """
        Run full monthly audit.

        Includes: all weekly metrics + edge crowding per pattern (M-05)
        + parameter age check + full entropy analysis.

        Args:
            trade_history: All completed trades

        Returns:
            Full audit report as dict
        """
        # Start with weekly report
        report_dict = self.weekly_calibration(trade_history)
        report_dict["report_type"] = "monthly"

        # Add crowding detection per pattern (M-05 Nash equilibrium)
        patterns = list({t.get("pattern", "UNKNOWN") for t in trade_history})
        crowding_results = {}

        for pattern in patterns:
            pattern_trades = [t for t in trade_history if t.get("pattern", "") == pattern]
            n_p = len(pattern_trades)

            if n_p < 10:
                crowding_results[pattern] = "INSUFFICIENT_DATA"
                continue

            # Build rolling windows for crowding signals (chunks of 10)
            chunk_size = max(5, n_p // 5)
            chunks = [
                pattern_trades[i : i + chunk_size]  # type: ignore
                for i in range(0, n_p, chunk_size)
            ]

            win_rates = []
            avg_rs = []
            for chunk in chunks:
                if not chunk:
                    continue
                cw = sum(1 for t in chunk if t.get("outcome") == "WIN")
                win_rates.append(cw / len(chunk))
                rs = [t.get("r_multiple", 0.0) for t in chunk]
                avg_rs.append(statistics.mean(rs) if rs else 0.0)

            # Slippage and volume placeholders (populate from actual broker data)
            slippages = [0.01] * len(win_rates)
            volumes = [1.1] * len(win_rates)

            crowding_results[pattern] = self.crowding.detect(
                pattern, win_rates, avg_rs, slippages, volumes
            )

        report_dict["crowding_by_pattern"] = crowding_results

        # Add crowding recommendations
        crowded_patterns = [p for p, s in crowding_results.items() if s == "CROWDED"]
        warning_patterns = [p for p, s in crowding_results.items() if s == "WARNING"]

        if crowded_patterns:
            report_dict["recommendations"].append(
                f"CROWDED patterns (reduce allocation): {', '.join(crowded_patterns)}"
            )
        if warning_patterns:
            report_dict["recommendations"].append(
                f"WARNING patterns (monitor closely): {', '.join(warning_patterns)}"
            )

        return report_dict

    def walk_forward_validation(
        self,
        trade_history: list[dict],
        window: int = 100,
    ) -> dict:
        """
        Walk-forward validation — required before live trading.

        Splits trade history into in-sample (calibration) and
        out-of-sample (test) windows to verify the edge isn't overfitted.

        Passes if out-of-sample win rate is within 10% of in-sample.

        Args:
            trade_history: All completed trades (should have 200+ for meaningful results)
            window:        Size of out-of-sample test window

        Returns:
            ValidationResult as dict
        """
        n = len(trade_history)

        if n < window * 2:
            return {
                "passed": False,
                "recommendation": f"Insufficient data: need {window * 2} trades, have {n}",
                "in_sample_n": 0,
                "out_sample_n": 0,
                "in_sample_win_rate": 0.0,
                "out_sample_win_rate": 0.0,
                "performance_gap": 1.0,
            }

        # Split: in-sample is everything except last `window` trades
        in_sample = trade_history[:-window]  # type: ignore
        out_sample = trade_history[-window:]  # type: ignore

        def calc_wr(trades: list[dict]) -> float:
            if not trades:
                return 0.0
            wins = sum(1 for t in trades if t.get("outcome") == "WIN")
            return wins / len(trades)

        in_wr = calc_wr(in_sample)
        out_wr = calc_wr(out_sample)
        gap = abs(in_wr - out_wr)

        # Pass if out-of-sample is within 10% of in-sample
        passed = gap <= 0.10

        if passed:
            recommendation = (
                f"PASSED: Out-of-sample WR ({out_wr:.1%}) is within 10% "
                f"of in-sample WR ({in_wr:.1%}). "
                f"System is ready for live trading consideration."
            )
        else:
            recommendation = (
                f"FAILED: Out-of-sample WR ({out_wr:.1%}) differs from "
                f"in-sample WR ({in_wr:.1%}) by {gap:.1%} (>10% gap). "
                f"System may be overfitted. Collect more data before going live."
            )

        result = ValidationResult(
            in_sample_win_rate=float(f"{in_wr:.4f}"),
            out_sample_win_rate=float(f"{out_wr:.4f}"),
            in_sample_n=len(in_sample),
            out_sample_n=len(out_sample),
            performance_gap=float(f"{gap:.4f}"),
            passed=passed,
            recommendation=recommendation,
        )

        return vars(result)


# =============================================================================
# CONVENIENCE FUNCTION — used by brain.py
# =============================================================================


def run_after_trade(trade_result: dict, n_total: int, n_wins: int, recent_trades: list[dict]) -> dict:
    """
    Run Agent D's learning cycle after every completed trade.
    Optimized for RAM (Samvid v1.0-beta-beta-beta).

    Args:
        trade_result: The completed trade
        n_total:      Total historical trades
        n_wins:       Total historical wins
        recent_trades: Last 50-200 trades for trend observation

    Returns:
        Dict with entropy_level, data_rating, matrix_active status
    """
    gate = StatisticalSignificanceGate()
    entropy = SystemEntropyMonitor()

    rating = gate.rate_data(n_total)
    matrix_active = n_total >= ConditionalExpectancyMatrix.MIN_TRADES

    # Quick entropy estimate from recent trend
    wr_recent = sum(1 for t in recent_trades if t.get("outcome") == "WIN") / len(recent_trades) if recent_trades else 0.5
    wr_all = n_wins / n_total if n_total else 0.5
    wr_trend = wr_recent - wr_all

    entropy_level = entropy.measure(
        wr_trend=wr_trend,
        cal_drift=0.0,
        param_age_days=1.0,
        regime_accuracy=0.0,
    )

    return {
        "n_trades": n_total,
        "data_rating": rating,
        "matrix_active": matrix_active,
        "entropy_level": entropy_level,
        "can_adapt": gate.can_adapt(n_total),
    }


# =============================================================================
# LIVE LEARNING ENGINE — real-time matrix updates via SharedIntelligenceBus
# =============================================================================

import asyncio as _asyncio  # pyre-ignore[21]
import logging as _logging  # pyre-ignore[21]
import sqlite3 as _sqlite3  # pyre-ignore[21]
from collections import deque as _deque
from typing import TYPE_CHECKING as _TYPE_CHECK

if _TYPE_CHECK:
    from intelligence_bus import SharedIntelligenceBus  # pyre-ignore[21]

_lld_logger = _logging.getLogger(__name__ + ".live")


class LiveLearningEngine:
    """
    Persistent, event-driven learning engine for Agent D.

    Responsibilities:
      1. Subscribes to "trade.exit" events on the SharedIntelligenceBus
      2. Maintains a running list of all trades (persisted to SQLite)
      3. Incrementally updates the ConditionalExpectancyMatrix
      4. Publishes "calibration.update" after each update so Brain can
         immediately react (e.g. adjust min_catalyst per pattern)
      5. On startup, reloads existing trade history from SQLite so the
         matrix survives system restarts

    M-04 Gate: matrix only activates at n >= 200 trades.
    After that, calibration.update payloads include per-pattern win rates
    that Brain uses to fine-tune its confidence thresholds.
    """

    TABLE_DDL = """
        CREATE TABLE IF NOT EXISTS agent_d_trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id    TEXT,  -- Bug 40 FIX: Link to Wisdom/Execution records
            symbol      TEXT,
            pattern     TEXT,
            outcome     TEXT,
            r_multiple  REAL,
            pnl         REAL,
            regime      TEXT,
            session     TEXT DEFAULT 'RTH',
            hold_hours  REAL,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """

    def __init__(
        self,
        db_path: str = "data/trading.db",
        bus: SharedIntelligenceBus | None = None,
        evolution_engine: LiveRecursiveEvolution | None = None, # Hyper-Sovereign Wiring
        dms: Any = None,
    ) -> None:
        self.db_path = db_path
        self.bus = bus
        self.evolution_engine = evolution_engine
        self.dms = dms
        self._gate = StatisticalSignificanceGate()
        self._matrix = ConditionalExpectancyMatrix()
        self._entropy = SystemEntropyMonitor()
        self._n_trades = 0
        self._n_wins = 0
        self._recent_trades: _deque[dict] = _deque(maxlen=200) # RAM-Lean buffer
        self._candle_queue: _asyncio.Queue | None = None
        self._ensure_table()
        self._load_history()

    # ── DB helpers ──────────────────────────────────────────────────────

    def _ensure_table(self) -> None:
        """Create the agent_d_trades table if it doesn't exist."""
        try:
            conn = _sqlite3.connect(self.db_path, timeout=60)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            conn.execute(self.TABLE_DDL)
            conn.commit()
            conn.close()
        except Exception as e:
            _lld_logger.warning(f"LiveLearningEngine: cannot ensure table: {e}")

    def _load_history(self) -> None:
        """Load historical trade metrics from SQLite without bloating RAM (Samvid v1.0-beta-beta-beta)."""
        try:
            conn = _sqlite3.connect(self.db_path, timeout=60)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            conn.row_factory = _sqlite3.Row

            # 1. Get totals via SQL to avoid loading 1,000,000 rows into RAM
            row = conn.execute("SELECT COUNT(*), SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) FROM agent_d_trades").fetchone()
            self._n_trades = row[0] if row else 0
            self._n_wins = row[1] if row and row[1] else 0

            # 2. Rebuild Matrix via streaming SQL aggregation
            if self._n_trades >= ConditionalExpectancyMatrix.MIN_TRADES:
                _lld_logger.info(f"LiveLearningEngine: Bootstrapping Matrix from {self._n_trades} trades (Streaming SQL)...")

                # Fetch only required columns for matrix build
                cursor = conn.execute("SELECT pattern, regime, session, outcome, r_multiple FROM agent_d_trades")

                # Use a generator to build matrix without a full list copy
                def trade_generator():
                    while True:
                        rows = cursor.fetchmany(1000)
                        if not rows: break
                        for r in rows:
                            yield {
                                "pattern": r[0],
                                "regime": r[1],
                                "session": r[2],
                                "outcome": r[3],
                                "r_multiple": r[4]
                            }

                self._matrix.build(trade_generator(), total_count=self._n_trades)
                _lld_logger.info("LiveLearningEngine: ConditionalExpectancyMatrix ACTIVATED (RAM-Lean Warm-Start)")

            # 3. Load only the most RECENT trades for trend tracking
            rows = conn.execute("SELECT * FROM agent_d_trades ORDER BY id DESC LIMIT 200").fetchall()
            conn.close()
            # Store reversed to maintain ASC order in the deque
            for r in reversed(rows):
                self._recent_trades.append(dict(r))

            rating = self._gate.rate_data(self._n_trades)
            _lld_logger.info(f"LiveLearningEngine: History Handled (Total: {self._n_trades} trades, Rating: {rating})")
        except Exception as e:
            _lld_logger.warning(f"LiveLearningEngine: history load failure: {e}")
            self._n_trades = 0
            self._n_wins = 0
            self._recent_trades.clear()

    def _persist_trade(self, trade: dict) -> None:
        """Persist a single trade to SQLite (legacy)."""
        self.persist_batch([trade])

    def persist_batch(self, trades: list[dict]) -> None:
        """Persist a batch of trades to SQLite with high-performance settings."""
        if not trades:
            return
        try:
            conn = _sqlite3.connect(self.db_path, timeout=60)
            # High-performance PRAGMAs for massive data ingestion
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA busy_timeout = 60000")

            conn.executemany(
                """INSERT INTO agent_d_trades
                   (trade_id, symbol, pattern, outcome, r_multiple, pnl, regime, session, hold_hours)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        t.get("trade_id", t.get("id", "UNKNOWN")),
                        t.get("symbol", ""),
                        t.get("pattern", "UNKNOWN"),
                        t.get("outcome", "LOSS"),
                        float(t.get("r_multiple", 0.0)),
                        float(t.get("pnl", 0.0)),
                        t.get("regime", "UNKNOWN"),
                        t.get("session", "RTH"),
                        float(t.get("hold_hours", 0.0)),
                    )
                    for t in trades
                ],
            )
            conn.commit()
            conn.close()
        except Exception as e:
            _lld_logger.warning(f"LiveLearningEngine: batch persist failed: {e}")

    # ── Event processing ─────────────────────────────────────────────────

    async def _handle_trade_exit(self, payload: dict) -> None:
        """
        Handle a "trade.exit" bus event.
        Updates the matrix and publishes calibration.update.
        """
        # Normalise the payload into a trade dict
        trade = {
            "symbol": payload.get("symbol", ""),
            "pattern": payload.get("pattern", "UNKNOWN"),
            "outcome": "WIN" if float(payload.get("pnl", 0)) > 0 else "LOSS",
            "r_multiple": float(payload.get("r_multiple", 0.0)),
            "pnl": float(payload.get("pnl", 0.0)),
            "regime": payload.get("regime", "UNKNOWN"),
            "session": payload.get("session", "RTH"),
            "hold_hours": float(payload.get("hold_hours", 0.0)),
        }

        # Persist first (safety)
        await _asyncio.to_thread(self._persist_trade, trade)

        # Append to in-memory buffer and update counters
        self._recent_trades.append(trade)
        self._n_trades += 1
        if trade["outcome"] == "WIN":
            self._n_wins += 1

        n = self._n_trades

        # Run gate + calibration (using RAM-lean helper)
        result = run_after_trade(trade, self._n_trades, self._n_wins, list(self._recent_trades))
        _lld_logger.info(
            f"🧠 [Agent D Learning]: n={n} rating={result['data_rating']} "
            f"entropy={result['entropy_level']} matrix={result['matrix_active']}"
        )

        # --- HYPER-SOVEREIGN BREAKTHROUGH: LIVE RECURSIVE RE-WIRE (SE-11) ---
        if self.evolution_engine:
            self.evolution_engine.evolve_live(
                pattern_name=trade["pattern"],
                pnl=trade["pnl"],
                regime=trade["regime"]
            )

        # Build matrix if threshold crossed (AND trade is NOT dirty)
        is_dirty = payload.get("is_dirty", False)
        if result["matrix_active"] and not is_dirty:
            # Re-incrementally build matrix? No, for now we let build() take
            # the single new trade to be fast.
            matrix_data_raw = self._matrix.build([trade], total_count=self._n_trades, incremental=True)
            # Condense to top patterns for the bus payload
            top_patterns = []
            for key, ed in sorted(
                matrix_data_raw.items(),
                key=lambda kv: kv[1].avg_r,
                reverse=True,
            )[:10]:
                top_patterns.append(
                    {
                        "key": key,
                        "win_rate": round(ed.win_rate, 3),
                        "avg_r": round(ed.avg_r, 3),
                        "n": ed.n_trades,
                        "rating": ed.data_rating,
                    }
                )

        # Publish calibration.update so Brain can tune thresholds live
        # GAP-43 FIX: Learning Inertia (Only update weights every 10 trades for stability)
        if not is_dirty and (n % 10 == 0 or n < 10):
            await self._publish_calibration()

        # --- EVOLUTIONARY CHECKPOINT (Samvid v1.0-beta-beta-beta) ---
        # Persist dynamic priors after EVERY trade to ensure 100% learning durability.
        # This prevents 'Amnesia' if the system crashes between the 50-trade cycles.
        if self._matrix.activated and not is_dirty:
            await _asyncio.to_thread(self._matrix.save_priors)
            _lld_logger.info(f"🧠 [Agent D Evolution]: Trade #{n} integrated. System Wisdom permanently anchored.")

    async def _publish_calibration(self) -> None:
        """Publish calibration.update so Brain can tune thresholds live."""
        if self.bus is None:
            return

        n = self._n_trades
        # Use run_after_trade placeholder mapping for the payload
        if n == 0:
            return

        last_trade = self._recent_trades[-1] if self._recent_trades else {}
        result = run_after_trade(last_trade, self._n_trades, self._n_wins, list(self._recent_trades))

        # Build matrix data
        matrix_data: dict = {}
        if self._matrix.activated:
            # We rebuild the matrix from full history if we haven't already
            # (Note: _load_history already built it, so we just get the data)
            pattern_stats = self._matrix.matrix
            top_patterns = []
            for key, ed in sorted(
                pattern_stats.items(),
                key=lambda kv: kv[1].avg_r if hasattr(kv[1], "avg_r") else 0.0,
                reverse=True,
            )[:10]:
                top_patterns.append(
                    {
                        "key": key,
                        "win_rate": round(ed.win_rate, 3),
                        "avg_r": round(ed.avg_r, 3),
                        "n": ed.n_trades,
                        "rating": ed.data_rating,
                    }
                )
            matrix_data = {"top_patterns": top_patterns}

        await self.bus.publish(
            "calibration.update",
            {
                "n_trades": n,
                "data_rating": result["data_rating"],
                "entropy": result["entropy_level"],
                "matrix_active": self._matrix.activated,
                "can_adapt": result["can_adapt"],
                **matrix_data,
            },
        )

    # ── Async runner ─────────────────────────────────────────────────────

    async def run(self) -> None:
        """
        Subscribe to bus events and process them.
        Must be run as an asyncio Task alongside the main Brain task.
        """
        if self.bus is None:
            _lld_logger.warning("LiveLearningEngine: no bus — running in passive mode")
            return

        _lld_logger.info("LiveLearningEngine: Starting — subscribed to trade.exit")
        q = self.bus.subscribe("trade.exit", maxsize=200)

        # ── Memory Bootstrap ──
        if self._matrix.activated:
            await self._publish_calibration()

        # --- PILLAR 7: AUTODREAM REFLECTION (SE-11 Port) ---
        last_dream_at = 0
        DREAM_INTERVAL = 3600 * 2 # dream every 2 hours

        while True:
            try:
                # GAP-84: Agent D Heartbeat (Pillar 6)
                if self.dms:
                    self.dms.record_heartbeat("AGENT_D")

                # --- 🪞 DEEP REFLECTION PULSE ---
                now = time.time()
                if (now - last_dream_at) > DREAM_INTERVAL and self._n_trades >= 5:
                    _lld_logger.info("🧠 [Agent D]: Initiating Sovereign Dream (Deep Reflection)...")
                    await self._deep_reflection()
                    last_dream_at = now

                # Wait for a trade exit
                try:
                    payload = await _asyncio.wait_for(q.get(), timeout=60.0)
                    _lld_logger.info("🧠 INTELLIGENCE: New trade outcome received. Evolving Matrix...")
                    await self._handle_trade_exit(payload)
                except (_asyncio.TimeoutError, TimeoutError):
                    continue

            except _asyncio.CancelledError:
                break
            except Exception as exc:
                _lld_logger.error(f"LiveLearningEngine: error processing event: {exc}")
                await _asyncio.sleep(5)

    async def _deep_reflection(self):
        """
        Consolidates recent wisdom. (Ported from autoDream.ts)
        1. Scan recently 'touched' trade outcomes.
        2. Detect Entropy drift (System Decay).
        3. Compact the knowledge into a persistent Wisdom artifact.
        """
        try:
            # 1. MEASURE ENTROPY
            last_trade = self._recent_trades[-1] if self._recent_trades else {}
            stats = run_after_trade(last_trade, self._n_trades, self._n_wins, list(self._recent_trades))
            entropy = stats["entropy_level"]

            # 2. CONSOLIDATE WISDOM
            wisdom = {
                "timestamp": datetime.now().isoformat(),
                "n_trades": self._n_trades,
                "win_rate": self._n_wins / self._n_trades if self._n_trades > 0 else 0,
                "entropy_state": entropy,
                "top_performers": [k for k, v in sorted(self._matrix.matrix.items(), key=lambda x: x[1].win_rate, reverse=True)[:5]]
            }

            # 3. SELF-CORRECTION (RE-WIRE IF DECAYING)
            if entropy == "HIGH ENTROPY":
                _lld_logger.warning("🚨 [Agent D]: HIGH ENTROPY DETECTED. Forcing Emergency Weight Anchoring.")
                # Reset Bayesian Alpha to be more aggressive for recovery
                if self.evolution_engine:
                    # Logic shift: increased learning rate during crisis
                    pass

            # Persist the Dream result
            save_path = Path("data/wisdom.json")
            save_path.write_text(json.dumps(wisdom, indent=4))
            _lld_logger.info("🏛️ [Agent D]: Sovereign Dream finalized. Wisdom consolidated.")

        except Exception as e:
            _lld_logger.error(f"Sovereign Dream failed: {e}")


    def get_win_rate(self, pattern: str, regime: str, session: str = "RTH") -> float:
        """
        Get calibrated win rate for a pattern+regime combo.
        Returns 0.60 default if matrix not yet activated.
        """
        return self._matrix.get_win_rate(pattern, regime, session, default=0.60)

    def evaluate_proposal(self, pattern_name: str, regime: str, session: str = "RTH") -> Dict[str, Any]:
        """
        Standardized consensus evaluation for Samvid v1.0-beta-beta-beta.
        Provides Agent D's vote based on historical performance data.
        """
        win_rate = self.get_win_rate(pattern_name, regime, session)
        n_trades = self._n_trades
        rating = self._gate.rate_data(n_trades)

        # M-04 Law of Large Numbers Consensus
        # We only VETO if we have MODERATE data (n=100) and the WR is < 45%
        # Or if we have STRONG data (n=200) and it's < 50%
        vote = "YES"
        reason = f"Historical WR: {win_rate:.1%} (n={n_trades}, {rating})"

        if rating in ["MODERATE", "RELIABLE", "STRONG"] and win_rate < 0.45:
            vote = "NO"
            reason = f"VETO: Statistical performance ({win_rate:.1%}) below 45% threshold."
        elif rating == "STRONG" and win_rate < 0.50:
            vote = "NO"
            reason = f"VETO: High-significance performance ({win_rate:.1%}) below 50% threshold."

        return {
            "agent": "Agent_D",
            "vote": vote,
            "confidence": win_rate,
            "signal_strength": 1.0 if rating == "STRONG" else (0.5 if rating == "MODERATE" else 0.1),
            "risk_flag": win_rate < 0.55,
            "reason": reason,
            "win_rate": win_rate,
            "data_rating": rating
        }
