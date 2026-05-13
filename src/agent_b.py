"""
src/agent_b.py - Trading System Agent B
Implements Dhatu-based market analysis with Bayesian belief tracking,
ABHAVA (absence) detection, and catalyst scoring following F3 order.
Part of a trading system incorporating Project Dhatu principles:
- Sutra compression
- ABHAVA analysis (tracking what's ABSENT)
- Anuvṛtti context flow
"""

import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from dhatu_oracle import DhatuOracle
# (debug instrumentation removed after verified fix)


class StateType(Enum):
    """Dhatu state types representing market conditions."""

    GROWTH = "growth"  # Vriddhi - expansion/growth
    DECAY = "decay"  # Kshaya - contraction/decay
    STABLE = "stable"  # Sthira - stability
    VOLATILE = "volatile"  # Chala - movement/volatility
    ABSENT = "absent"  # Abhava - absence (critical for ABHAVA detection)
    CONJUNCTION = "conjunction"  # Samyoga - coming together
    SEPARATION = "separation"  # Viyoga - separation/divergence
    PERSISTENCE = "persistence"  # Sthiti - continuation/persistence


@dataclass
class DhatuState:
    """
    Represents a Dhatu market state with freshness tracking.
    Dhatu states encode market conditions using ancient computational paradigms
    that track both presence AND absence of market factors.
    Attributes:
        name: The Sanskrit name of the state (e.g., 'Vriddhi', 'Kshaya')
        state_type: Enumerated type categorizing the state
        base_modifier: Base multiplier for this state (0.0-2.0 typical range)
        freshness_score: How recent/relevant the state assessment is (0.0-1.0)
        detected_at: Timestamp when state was classified
        confidence: Classification confidence level (0.0-1.0)
    """

    name: str
    state_type: StateType
    base_modifier: float
    freshness_score: float
    detected_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.5

    def __post_init__(self):
        """Validate state parameters."""
        if not 0.0 <= self.freshness_score <= 1.0:
            raise ValueError(f"freshness_score must be 0.0-1.0, got {self.freshness_score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")

    @property
    def effective_modifier(self) -> float:
        """
        Calculate effective modifier accounting for freshness decay.
        Decays towards 1.0 (neutrality) as time passes, rather than towards 0.0.
        Formula: 1.0 + (base_modifier - 1.0) * freshness_score
        """
        return 1.0 + (self.base_modifier - 1.0) * self.freshness_score

    @property
    def is_stale(self) -> bool:
        """Check if state needs refresh (freshness below threshold)."""
        return self.freshness_score < 0.35


class DhatuClassifier:
    """
    Classifies market data into one of 8 Dhatu states.
    The 8 states represent fundamental market conditions:
    - Vriddhi (growth): Strong upward momentum
    - Kshaya (decay): Deteriorating conditions
    - Sthira (stable): Low volatility, range-bound
    - Chala (volatile): High volatility, directional uncertainty
    - Abhava (absent): Missing expected catalyst/activity (CRITICAL)
    - Samyoga (conjunction): Multiple factors aligning
    - Viyoga (separation): Divergence between indicators
    - Sthiti (persistence): Continuation of prior state
    Implements sutra freshness scoring per F17/F18 specifications.
    """

    # State thresholds calibrated from 147 historical events
    VRIDDHI_MOMENTUM_THRESHOLD = 0.002  # 0.2% positive momentum (intraday 1m scale)
    KSHAYA_MOMENTUM_THRESHOLD = -0.002  # -0.2% negative momentum (intraday 1m scale)
    VOLATILITY_HIGH_THRESHOLD = 0.0025  # 0.25% daily range (intraday 1m scale)
    VOLATILITY_LOW_THRESHOLD = 0.0008  # 0.08% daily range (intraday 1m scale)
    VOLUME_RATIO_SIGNIFICANT = 1.5  # 150% of average volume

    # Base modifiers for each state (from 17 master sutras)
    STATE_BASE_MODIFIERS: dict[str, float] = {
        "Vriddhi": 1.15,  # Growth enhances catalyst scores
        "Kshaya": 0.75,  # Decay reduces catalyst scores
        "Sthira": 1.00,  # Stable - neutral effect
        "Chala": 0.85,  # Volatility adds uncertainty discount
        "Abhava": 1.25,  # Absence of catalyst is informative (gap fade pattern)
        "Samyoga": 1.20,  # Alignment of factors is bullish
        "Viyoga": 0.70,  # Divergence is bearish
        "Sthiti": 0.95,  # Persistence slight discount (mean reversion)
    }

    def __init__(
        self, sutra_decay_halflife_hours: float = 24.0, oracle: "DhatuOracle | None" = None
    ) -> None:
        """
        Initialize classifier with configurable freshness decay and optional Oracle.
        Args:
            sutra_decay_halflife_hours: Hours until sutra freshness halves
            oracle: DhatuOracle instance for global macro awareness
        """
        self.sutra_decay_halflife = sutra_decay_halflife_hours
        self.oracle = oracle
        self._last_state: DhatuState | None = None
        self._state_history: list[DhatuState] = []

    def classify(self, market_data: dict[str, Any]) -> DhatuState:
        """
        Classify market conditions into a Dhatu state.
        Args:
            market_data: Dictionary containing:
                - price_change: float (percentage change)
                - volatility: float (daily range as percentage)
                - volume_ratio: float (current vs average volume)
                - has_catalyst: bool (whether fundamental catalyst exists)
                - rsi: float (0-100, optional)
                - breadth: float (market breadth, optional)
                - hours_since_event: float (age of relevant event, optional)
        Returns:
            DhatuState representing current market classification
        """
        price_change = market_data.get("price_change", 0.0)
        volatility = market_data.get("volatility", 0.015)
        volume_ratio = market_data.get("volume_ratio", 1.0)
        has_catalyst = market_data.get("has_catalyst", True)
        rsi = market_data.get("rsi", 50.0)
        hours_since = market_data.get("hours_since_event", 0.0)

        # Calculate freshness based on event age
        freshness = self.sutra_freshness_score(hours_since)

        # ABHAVA detection: tracking what is ABSENT
        # Case A: Price moves significantly without an underlying catalyst (Gap Fade)
        # Case B: Strong catalyst exists but price fails to respond (Exhaustion/Absence of Reaction)
        is_abhava = (not has_catalyst and abs(price_change) > 0.005) or (
            has_catalyst and abs(price_change) < 0.0005 and volume_ratio > 1.2
        )

        if is_abhava:
            state_name = "Abhava"
            confidence = min(0.90, 0.6 + abs(price_change) * 5)

        # Samyoga: Multiple factors aligning (Growth + Volume + RSI cushion)
        elif (
            price_change > self.VRIDDHI_MOMENTUM_THRESHOLD
            and volume_ratio > self.VOLUME_RATIO_SIGNIFICANT
            and rsi < 70
        ):
            state_name = "Samyoga"
            confidence = min(0.85, 0.5 + price_change * 10 + (volume_ratio - 1) * 0.2)

        # Viyoga: Price/volume divergence (The Sovereign Divergence)
        elif (price_change > 0.01 and volume_ratio < 0.7) or (
            price_change < -0.01 and volume_ratio > 1.5
        ):
            state_name = "Viyoga"
            confidence = 0.65

        # Vriddhi: Growth (with 10% Hysteresis override)
        elif price_change > (self.VRIDDHI_MOMENTUM_THRESHOLD * 0.9):
            state_name = "Vriddhi"
            confidence = min(0.80, 0.5 + price_change * 15)

        # Kshaya: Decay (with 10% Hysteresis override)
        elif price_change < (self.KSHAYA_MOMENTUM_THRESHOLD * 0.9):
            state_name = "Kshaya"
            confidence = min(0.80, 0.5 + abs(price_change) * 15)

        # Chala: High volatility (The Sovereign Chaos)
        elif volatility > (self.VOLATILITY_HIGH_THRESHOLD * 0.9):
            state_name = "Chala"
            confidence = min(0.75, 0.5 + volatility * 10)

        # Sthira: Low volatility (The Sovereign Stillness)
        elif volatility < (self.VOLATILITY_LOW_THRESHOLD * 1.1):
            state_name = "Sthira"
            confidence = min(0.80, 0.6 + (self.VOLATILITY_LOW_THRESHOLD - volatility) * 50)

        else:
            state_name = "Sthiti"
            confidence = 0.50

        state = DhatuState(
            name=state_name,
            state_type=self._name_to_type(state_name),
            base_modifier=self.STATE_BASE_MODIFIERS[state_name],
            freshness_score=freshness,
            confidence=confidence,
        )

        # Track state history for Anuvṛtti (context flow)
        self._last_state = state
        self._state_history.append(state)
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-100:]  # type: ignore

        return state

    def sutra_freshness_score(self, age_hours: float) -> float:
        """
        Calculate sutra freshness using exponential decay.
        Per F17: belief = min(0.90, posterior)
        Freshness decays exponentially with configurable half-life.
        Args:
            age_hours: Hours since the sutra/event was generated
        Returns:
            Freshness score between 0.0 and 1.0
        """
        if age_hours <= 0:
            return 1.0

        # Exponential decay: f(t) = e^(-λt) where λ = ln(2)/half_life
        h_life = max(0.1, self.sutra_decay_halflife)

        if age_hours > 1.0:
            h_life = min(h_life, 2.0)  # Force 2h max halflife for old news

        decay_constant = math.log(2) / h_life
        freshness = math.exp(-decay_constant * age_hours)

        # Floor at 0.05 - even old sutras retain minimal relevance
        return max(0.05, freshness)

    def dhatu_modifier(self, base: float, freshness: float) -> float:
        """
        Calculate Dhatu modifier per F18-Hardened:
        Decays towards 1.0 (neutrality) rather than 0.0.
        Args:
            base: Base modifier for the state (from STATE_BASE_MODIFIERS)
            freshness: Current freshness score (0.0-1.0)
        Returns:
            Effective modifier after freshness adjustment
        """
        return 1.0 + (base - 1.0) * freshness

    def _name_to_type(self, name: str) -> StateType:
        """Map state name to StateType enum."""
        mapping = {
            "Vriddhi": StateType.GROWTH,
            "Kshaya": StateType.DECAY,
            "Sthira": StateType.STABLE,
            "Chala": StateType.VOLATILE,
            "Abhava": StateType.ABSENT,
            "Samyoga": StateType.CONJUNCTION,
            "Viyoga": StateType.SEPARATION,
            "Sthiti": StateType.PERSISTENCE,
        }
        return mapping.get(name, StateType.STABLE)


class BayesianBeliefTracker:
    """
    Tracks belief probability using Bayesian updates.
    Implements F8 likelihood specifications for evidence types:
    - price_toward: Price moving toward target (small/medium/large)
    - price_against: Price moving against target (small/medium)
    - volume_confirming: Volume confirms price direction
    - vix_declining: VIX declining (bullish for longs)
    Critical thresholds:
    - EXIT if belief < 0.35
    - ADD if belief > 0.80
    - belief capped at 0.90 per F17
    """

    # F8 likelihood specifications (Base Values)
    BASE_LIKELIHOODS: dict[str, float] = {
        "price_toward_small": 0.58,
        "price_toward_medium": 0.72,
        "price_toward_large": 0.85,
        "price_against_small": 0.45,
        "price_against_medium": 0.30,
        "volume_confirming": 0.68,
        "vix_declining": 0.62,
    }

    # Action thresholds
    EXIT_THRESHOLD = 0.35
    ADD_THRESHOLD = 0.80
    MAX_BELIEF = 0.90  # F17: belief = min(0.90, posterior)

    def __init__(self, prior: float = 0.50) -> None:
        """
        Initialize tracker with prior belief.
        Args:
            prior: Initial belief probability (default 0.50 for maximum entropy)
        """
        if not 0.0 < prior < 1.0:
            raise ValueError(f"Prior must be between 0 and 1, got {prior}")

        self._belief = prior
        self._prior = prior
        self._update_history: list[dict[str, Any]] = []

    @property
    def current_belief(self) -> float:
        """Get current belief probability."""
        return self._belief

    def update(
        self, evidence_type: str, value: float | None = None, dhatu_state: str = "Sthira"
    ) -> str:
        """
        Update belief based on new evidence using Adaptive Bayesian Likelihoods.
        Likelihoods are scaled based on the current Dhatu state to prevent 'Drift'.
        """
        # 1. Resolve Base Likelihood
        if value is not None:
            likelihood = value
        elif hasattr(self, "BASE_LIKELIHOODS") and evidence_type in self.BASE_LIKELIHOODS:
            likelihood = self.BASE_LIKELIHOODS[evidence_type]
        elif hasattr(self, "LIKELIHOODS") and evidence_type in self.LIKELIHOODS:
            likelihood = self.LIKELIHOODS[evidence_type]
        else:
            # Fallback to local dict if class attr not yet updated in this run
            temp_lik = {
                "price_toward_small": 0.58,
                "price_toward_medium": 0.72,
                "price_toward_large": 0.85,
                "price_against_small": 0.45,
                "price_against_medium": 0.30,
                "volume_confirming": 0.68,
                "vix_declining": 0.62,
            }
            likelihood = temp_lik.get(evidence_type, 0.5)

        # In Volatile markets (Chala/Kshaya), we compress likelihoods toward 0.5 (Noise)
        # In Stable markets (Sthira/Samyoga), we expand likelihoods (Signal)
        scaling_factor = 1.0
        if dhatu_state in ("Chala", "Kshaya"):
            scaling_factor = 0.7  # Compress by 30%
        elif dhatu_state in ("Sthira", "Samyoga", "Vriddhi"):
            scaling_factor = 1.2  # Expand by 20%

        # P(E|H) = 0.5 + (BaseLikelihood - 0.5) * Scaling
        likelihood = 0.5 + (likelihood - 0.5) * scaling_factor
        likelihood = max(0.1, min(0.9, likelihood))

        # 3. Bayesian update
        # P(E) = P(E|H)*P(H) + P(E|~H)*P(~H)
        # Assuming P(E|~H) = 1 - P(E|H) for binary evidence
        p_e_given_h = likelihood
        p_e_given_not_h = 1.0 - likelihood

        prior = self._belief

        # Calculate evidence probability
        p_e = p_e_given_h * prior + p_e_given_not_h * (1 - prior)

        # Avoid division by zero
        p_e = max(p_e, 1e-10)

        # Calculate posterior
        posterior = (p_e_given_h * prior) / p_e

        # F17: belief = min(0.90, posterior)
        self._belief = max(0.01, min(self.MAX_BELIEF, posterior))

        # Record update for analysis
        self._update_history.append(
            {
                "evidence_type": evidence_type,
                "likelihood": likelihood,
                "prior": prior,
                "posterior": self._belief,
                "timestamp": datetime.now(),
            }
        )

        # Determine action
        if self._belief < self.EXIT_THRESHOLD:
            return "EXIT"
        elif self._belief > self.ADD_THRESHOLD:
            return "ADD"
        else:
            return "HOLD"

    def reset(self, new_prior: float | None = None) -> None:
        """Reset belief to initial prior or new value."""
        self._belief = new_prior if new_prior is not None else self._prior
        self._update_history.clear()

    def get_history(self) -> list[dict[str, Any]]:
        """Get update history for analysis."""
        return self._update_history.copy()

    async def evaluate_proposal(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Provides Agent B's Bayesian belief vote.
        """
        from datetime import timezone

        temp_tracker = BayesianBeliefTracker(prior=self._prior)

        ohlcv = context.get("ohlcv_df") or context.get("ohlcv_1m")
        if ohlcv is not None and len(ohlcv) >= 5:
            try:
                # 1. Market Data Extraction
                last_close = float(ohlcv["close"][-1])
                prev_close = float(ohlcv["close"][-2])
                price_change = (last_close - prev_close) / (prev_close + 1e-10)

                # Volatility (20-bar range)
                h20 = float(ohlcv["high"][-20:].max())
                l20 = float(ohlcv["low"][-20:].min())
                volatility = (h20 - l20) / (last_close + 1e-10)

                # Volume Ratio
                avg_vol = float(ohlcv["volume"][-20:].mean())
                curr_vol = float(ohlcv["volume"][-1])
                vol_ratio = curr_vol / (avg_vol + 1e-10)

                # 2. Dhatu Classification
                # Note: We use local instances to keep evaluate_proposal pure and stateless
                classifier = DhatuClassifier()
                state = classifier.classify(
                    {
                        "price_change": price_change,
                        "volatility": volatility,
                        "volume_ratio": vol_ratio,
                        "has_catalyst": True,  # Default assumption for proposal vetting
                    }
                )

                # 3. Evidence Updates
                is_long = context.get("is_long", True)
                direction_match = (is_long and price_change > 0) or (
                    not is_long and price_change < 0
                )

                if direction_match:
                    temp_tracker.update("price_toward_small", dhatu_state=state.name)
                else:
                    temp_tracker.update("price_against_small", dhatu_state=state.name)

                if vol_ratio > 1.2:
                    temp_tracker.update("volume_confirming", dhatu_state=state.name)

                # 4. ABHAVA Integration
                # Convert last 5 bars to history list for detector
                history = []
                for i in range(max(0, len(ohlcv) - 5), len(ohlcv)):
                    p_curr = float(ohlcv["close"][i])
                    p_prev = float(ohlcv["close"][i - 1]) if i > 0 else p_curr
                    history.append(
                        {
                            "price_change": (p_curr - p_prev) / (p_prev + 1e-10),
                            "volume_ratio": float(ohlcv["volume"][i]) / (avg_vol + 1e-10),
                            "has_catalyst": True,
                        }
                    )

                abhava_det = ABHAVADetector()
                is_abhava = abhava_det.detect(history)

                belief = temp_tracker.current_belief
                if is_abhava and state.name == "Abhava":
                    # Critical Veto: Significant absence detected
                    belief = min(belief, 0.45)

                vote = "YES" if belief >= 0.5 else "NO"
                return {
                    "agent": "Agent_B",
                    "vote": vote,
                    "confidence": belief,
                    "reason": f"Dhatu: {state.name} | Belief: {belief:.2f} | ABHAVA: {is_abhava}",
                    "timestamp": time.time_ns(),
                }
            except Exception as e:
                # Fallback on calculation error
                belief = temp_tracker.current_belief
                vote = "YES" if belief >= 0.5 else "NO"
                return {
                    "agent": "Agent_B",
                    "vote": vote,
                    "confidence": belief,
                    "reason": f"Agent B Fallback (Error: {str(e)[:30]})",
                    "timestamp": time.time_ns(),
                }

        # Original fallback logic
        belief = temp_tracker.current_belief
        vote = "YES" if belief >= 0.5 else "NO"

        return {
            "agent": "Agent_B",
            "vote": vote,
            "confidence": belief,
            "reason": f"Bayesian Belief (Default): {belief:.2f}",
            "timestamp": context.get("timestamp", time.time_ns()),
        }


class ABHAVADetector:
    """
    Detects ABHAVA (absence) conditions in market data.
    ABHAVA is a critical Dhatu concept: tracking what's ABSENT.
    Standard systems only track presence; Dhatu tracks absence.
    Key ABHAVA patterns:
    - Gap without catalyst (Pattern 1: Gap Fade)
    - Volume absence during breakout (false breakout signal)
    - Catalyst absence during momentum (exhaustion signal)
    - News absence during volatility spike (manipulation signal)
    "No standard system does this" - Dhatu's key advantage
    """

    # Thresholds for absence detection
    GAP_THRESHOLD = 0.005  # 0.5% gap (intraday 1m scale)
    VOLUME_ABSENCE_RATIO = 0.5  # Below 50% average volume
    CATALYST_CHECK_WINDOW = 24  # Hours to look back for catalyst

    def __init__(self) -> None:
        """Initialize ABHAVA detector."""
        self._detections: list[dict[str, Any]] = []

    def detect(self, history: list[dict[str, Any]]) -> bool:
        """
        Detect ABHAVA (absence) condition in market history.
        Checks for the critical absence patterns that standard
        systems miss. Per Dhatu research: "ABHAVA: Tracking what's
        ABSENT — no standard system does this"
        Args:
            history: List of market data dictionaries, most recent last.
                Each dict should contain:
                - price_change: float
                - has_catalyst: bool
                - volume_ratio: float
                - timestamp: datetime (optional)
        Returns:
            True if ABHAVA (significant absence) detected
        """
        if not history:
            return False

        latest = history[-1]

        # Pattern 1: Gap without catalyst (Gap Fade setup)
        # "Opens 3%+ gap WITHOUT fundamental catalyst"
        price_change = latest.get("price_change", 0.0)
        has_catalyst = latest.get("has_catalyst", True)

        if abs(price_change) >= self.GAP_THRESHOLD and not has_catalyst:
            self._record_detection(
                "gap_no_catalyst",
                latest,
                f"Gap of {price_change:.1%} without catalyst - Gap Fade eligible",
            )
            return True

        # Pattern 2: Volume absence during price move
        # Breakout/breakdown without volume confirmation = false signal
        volume_ratio = latest.get("volume_ratio", 1.0)

        if abs(price_change) > 0.002 and volume_ratio < self.VOLUME_ABSENCE_RATIO:
            self._record_detection(
                "volume_absence",
                latest,
                f"Price move {price_change:.1%} with only {volume_ratio:.0%} volume",
            )
            return True

        # Pattern 3: Check for catalyst absence over declining period
        # "down >15% from high, decline 5+ days, no ongoing catalyst"
        if len(history) >= 5:
            total_decline = sum(h.get("price_change", 0) for h in history[-5:])  # type: ignore
            any_catalyst = any(h.get("has_catalyst", False) for h in history[-5:])  # type: ignore

            if total_decline < -0.015 and not any_catalyst:
                self._record_detection(
                    "decline_no_catalyst",
                    latest,
                    f"5-day decline of {total_decline:.1%} without catalyst - "
                    "Mean Reversion eligible",
                )
                return True

        # Pattern 4: Volatility spike without news
        volatility = latest.get("volatility", 0.015)
        if volatility > 0.04 and not has_catalyst:  # 4%+ daily range, no news
            self._record_detection(
                "volatility_no_news",
                latest,
                f"Volatility spike {volatility:.1%} without news - potential manipulation",
            )
            return True

        return False

    def _record_detection(
        self, detection_type: str, data: dict[str, Any], description: str
    ) -> None:
        """Record ABHAVA detection for analysis."""
        self._detections.append(
            {
                "type": detection_type,
                "data": data,
                "description": description,
                "timestamp": datetime.now(),
            }
        )

    def get_detections(self) -> list[dict[str, Any]]:
        """Get history of ABHAVA detections."""
        return self._detections.copy()

    def clear_detections(self) -> None:
        """Clear detection history."""
        self._detections.clear()


class InformationDecayModel:
    """
    Models the decay of information relevance over time.
    Information (catalysts, news, signals) loses relevance exponentially.
    High-entropy environments (volatile markets) accelerate decay.
    Used in F3 order for calculating final catalyst scores:
    decay factor is applied after base calculation.
    """

    # Base half-life in hours for different information types
    BASE_HALFLIFE_HOURS = 24.0

    # High entropy multiplier (faster decay in volatile markets)
    HIGH_ENTROPY_DECAY_MULTIPLIER = 2.0

    # Minimum decay factor (information never fully irrelevant)
    MIN_DECAY_FACTOR = 0.05

    def __init__(self, base_halflife: float = 24.0) -> None:
        """
        Initialize decay model.
        Args:
            base_halflife: Base half-life in hours for normal conditions
        """
        self.base_halflife = base_halflife

    def decay_factor(self, age_hours: float, high_entropy: bool = False) -> float:
        """
        Calculate decay factor for information of given age.
        Uses exponential decay: f(t) = e^(-λt)
        Where λ = ln(2) / half_life
        High entropy (volatile) environments double the decay rate,
        as information becomes stale faster when conditions change rapidly.
        Args:
            age_hours: Age of information in hours
            high_entropy: Whether market is in high-entropy (volatile) state
        Returns:
            Decay factor between MIN_DECAY_FACTOR and 1.0
        """
        if age_hours <= 0:
            return 1.0

        # Adjust half-life for high entropy environments
        effective_halflife = self.base_halflife
        if high_entropy:
            effective_halflife /= self.HIGH_ENTROPY_DECAY_MULTIPLIER

        # Calculate decay constant
        if age_hours > 1.0:
            effective_halflife = min(effective_halflife, 2.0)  # Force 2h max halflife for old news

        decay_constant = math.log(2) / effective_halflife

        # Exponential decay
        factor = math.exp(-decay_constant * age_hours)

        # Apply minimum floor
        return max(self.MIN_DECAY_FACTOR, factor)

    def time_to_threshold(self, threshold: float, high_entropy: bool = False) -> float:
        """
        Calculate hours until decay reaches threshold.
        Args:
            threshold: Target decay factor (e.g., 0.5 for half-life)
            high_entropy: Whether in high-entropy environment
        Returns:
            Hours until decay factor reaches threshold
        """
        if threshold >= 1.0:
            return 0.0
        if threshold <= self.MIN_DECAY_FACTOR:
            return float("inf")

        effective_halflife = self.base_halflife
        if high_entropy:
            effective_halflife /= self.HIGH_ENTROPY_DECAY_MULTIPLIER

        decay_constant = math.log(2) / effective_halflife

        # Solve: threshold = e^(-λt) => t = -ln(threshold)/λ
        return -math.log(threshold) / decay_constant


class CatalystScorer:
    """
    Scores catalysts following F3 ORDER specification.
    CRITICAL F3 ORDER:
    base -> modifiers -> decay -> dhatu*freshness -> escape -> compare
    This order is essential for correct scoring. Each step must
    execute in sequence with proper dependencies.
    Returns tuple of (score, passes_budget) for decision making.
    """

    # Escape class multipliers (pattern-specific adjustments)
    ESCAPE_CLASS_MULTIPLIERS: dict[str, float] = {
        "gap_fade": 1.10,  # Pattern 1: reliable, slight boost
        "mean_reversion": 1.05,  # Pattern 2: moderate reliability
        "catalyst_play": 1.15,  # Pattern 7: high conviction when catalyst confirmed
        "momentum": 0.95,  # Momentum plays slightly discounted
        "breakout": 0.90,  # Breakouts often fail
        "default": 1.00,  # No adjustment
    }

    def __init__(
        self,
        decay_model: InformationDecayModel | None = None,
        classifier: DhatuClassifier | None = None,
    ) -> None:
        """
        Initialize scorer with optional dependency injection.
        Args:
            decay_model: InformationDecayModel instance (created if None)
            classifier: DhatuClassifier instance (created if None)
        """
        self.decay_model = decay_model or InformationDecayModel()
        self.classifier = classifier or DhatuClassifier()

    def score(
        self,
        base_quality: float,
        modifiers: dict[str, float],
        age_hours: float,
        dhatu_state: DhatuState | None,
        escape_class: str,
        budget_min: float,
    ) -> Dict[str, Any]:
        """
        Score catalyst following F3 ORDER specification.
        CRITICAL F3 ORDER (must follow exactly):
        1. base - Start with base quality
        2. modifiers - Apply all modifier adjustments
        3. decay - Apply time-based decay
        4. dhatu*freshness - Apply Dhatu state modifier with freshness
        5. escape - Apply escape class multiplier
        6. compare - Compare against budget minimum
        Args:
            base_quality: Base catalyst quality score (0.0-100.0)
            modifiers: Dict of modifier_name -> adjustment_value
            age_hours: Age of catalyst information in hours
            dhatu_state: Current DhatuState from classifier
            escape_class: Pattern/escape class name (e.g., "gap_fade")
            budget_min: Minimum score required (from regime rules)
        Returns:
            Tuple of (final_score, passes_budget_check)
        """
        # STEP 1: BASE
        # Start with base quality score
        score = base_quality
        # Comment: F3 Step 1 - base quality established

        # STEP 2: MODIFIERS
        # Apply all modifier adjustments additively
        modifier_total = sum(modifiers.values())
        score += modifier_total
        # Comment: F3 Step 2 - modifiers applied (total: {modifier_total})

        # STEP 3: DECAY
        # Apply time-based decay factor
        # Determine if high entropy based on Dhatu state
        if dhatu_state is None:
            high_entropy = False
        else:
            high_entropy = dhatu_state.state_type == StateType.VOLATILE
        decay_factor = self.decay_model.decay_factor(age_hours, high_entropy)
        score *= decay_factor
        # Comment: F3 Step 3 - decay applied (factor: {decay_factor:.3f})

        # STEP 4: DHATU * FRESHNESS
        # Apply Dhatu modifier multiplied by freshness
        # Per F18: dhatu_modifier = base * freshness
        if dhatu_state is None:
            dhatu_mod = 1.0
        else:
            dhatu_mod = self.classifier.dhatu_modifier(
                dhatu_state.base_modifier, dhatu_state.freshness_score
            )
        score *= dhatu_mod
        # Comment: F3 Step 4 - dhatu*freshness applied (modifier: {dhatu_mod:.3f})

        # STEP 5: ESCAPE
        # Apply escape class multiplier
        escape_multiplier = self.ESCAPE_CLASS_MULTIPLIERS.get(
            escape_class.lower(), self.ESCAPE_CLASS_MULTIPLIERS["default"]
        )
        score *= escape_multiplier
        # Comment: F3 Step 5 - escape class '{escape_class}' applied (mult: {escape_multiplier})

        # STEP 5.5: GLOBAL DHATU ORACLE
        # Apply the macro risk modifier from the DhatuOracle
        global_multiplier = 1.0
        oracle: DhatuOracle | None = self.classifier.oracle
        if oracle is not None:
            mult: float = oracle.get_risk_modifier()
            global_multiplier = mult
        score *= global_multiplier
        # Comment: F3 Step 5.5 - global macro oracle applied (mult: {global_multiplier})

        # STEP 6: COMPARE
        # Compare against budget minimum
        passes_budget = score >= budget_min
        # Comment: F3 Step 6 - compare: {score:.2f} vs budget {budget_min} = {passes_budget}

        return {
            "agent": "Agent_B",
            "vote": "YES" if passes_budget else "NO",
            "confidence": min(0.99, score / 100.0) if score > 0 else 0.0,
            "signal_strength": min(2.0, score / budget_min) if budget_min > 0 else 1.0,
            "risk_flag": score < (budget_min * 1.05),  # Tight margin flag
            "reason": (
                f"Catalyst Score {score:.2f} (Min: {budget_min}) | "
                f"Dhatu: {dhatu_state.name if dhatu_state else 'None'}"
            ),
            "catalyst_score": score,
            "dhatu_state": dhatu_state.name if dhatu_state else "None",
        }

    def score_with_details(
        self,
        base_quality: float,
        modifiers: dict[str, float],
        age_hours: float,
        dhatu_state: DhatuState,
        escape_class: str,
        budget_min: float,
    ) -> dict[str, Any]:
        """
        Score catalyst with detailed breakdown of each step.
        Same as score() but returns full details for analysis/debugging.
        """
        details: dict[str, Any] = {
            "f3_order": "base->modifiers->decay->dhatu*freshness->escape->compare",
            "steps": [],
        }

        # Step 1: BASE
        score = base_quality
        details["steps"].append({"step": 1, "name": "base", "input": base_quality, "output": score})

        # Step 2: MODIFIERS
        modifier_total = sum(modifiers.values())
        score += modifier_total
        details["steps"].append(
            {
                "step": 2,
                "name": "modifiers",
                "modifiers": modifiers,
                "total_adjustment": modifier_total,
                "output": score,
            }
        )

        # Step 3: DECAY
        high_entropy = dhatu_state.state_type == StateType.VOLATILE
        decay_factor = self.decay_model.decay_factor(age_hours, high_entropy)
        score *= decay_factor
        details["steps"].append(
            {"step": 3, "name": "decay", "decay_factor": decay_factor, "output": score}
        )

        # Step 4: DHATU * FRESHNESS
        dhatu_mod = self.classifier.dhatu_modifier(
            dhatu_state.base_modifier, dhatu_state.freshness_score
        )
        score *= dhatu_mod
        details["steps"].append(
            {"step": 4, "name": "dhatu_time", "dhatu_multiplier": dhatu_mod, "output": score}
        )

        # Step 5: ESCAPE
        escape_multiplier = self.ESCAPE_CLASS_MULTIPLIERS.get(
            escape_class.lower(), self.ESCAPE_CLASS_MULTIPLIERS["default"]
        )
        score *= escape_multiplier
        details["steps"].append(
            {"step": 5, "name": "escape", "escape_multiplier": escape_multiplier, "output": score}
        )

        # Step 6: COMPARE
        passes_budget = score >= budget_min
        details["final_score"] = score
        details["passes_budget"] = passes_budget

        return details
