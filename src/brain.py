"""
src/brain.py - Trading System Coordinator
Central orchestrator that manages trading workflow, state transitions,
and coordinates all agents (A, B, C_IBKR, C_MT5, D) and Exit Intelligence.
Implements:
- Full state machine wired to actual agent calls
- Drawdown ladder tracking (IBKR + Prop)
- Consecutive loss graduated response
"""

import asyncio
import collections
import json
import logging
import os
import time
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    cast,
)

import numpy as np
import pandas as pd
import polars as pl
import pytz

logger = logging.getLogger(__name__)

from agent_a import (
    ContinuousBudgetMonitor,
    EscapeVelocityClassifier,
    FactorWeightCalibration,
    InMemorySovereignAtlas,
    MultiTimeframeAligner,
    NeuralRegimeClassifier,
    PatternDetector,
    PatternResult,
    SignalEntropyCalculator,
)
from agent_b import ABHAVADetector, BayesianBeliefTracker, DhatuClassifier
from agent_c import EvolutionManager
from agent_c_ibkr import (
    BlackSwanProtocol,
    CorrelationCascade,
    IBKRConnection,
    PortfolioGuard,
    PositionSizingChain,
    VIXProtocol,
)

# Imports are now lazy-loaded inside initialize_mt5_agents() to prevent unwanted terminal boot.
from agent_d import (
    EdgeCrowdingDetector,
    LiveLearningEngine,
    LiveRecursiveEvolution,
    RegimeClassifier,
    StatisticalSignificanceGate,
    SystemEntropyMonitor,
)
from agent_e import CorrelationGuard
from agent_h_skeptic import SkepticAgent
from config import (
    FORCED_PAPER_MODE,
    IBKR_MAX_TRADES_PER_DAY,
    QUESTDB_ENABLED,
    STARTING_CAPITAL_CAD,
)
from decision_ledger import LEDGER
from exit_intelligence import ExitAction, ExitIntelligence
from intelligence_bus import SharedIntelligenceBus
from llm_circuit_breaker import HEAVY_BREAKER, LIGHT_BREAKER  # noqa: F401
from memdir import MemoryManager
from mind_architect import MindArchitect
from mind_bridge import MindBridge
from mind_evolution import MindEvolution
from mind_experiment import MindExperiment
from mind_ghost import MindGhost
from mind_macros import MindMacros
from mind_math import MindMath
from mind_observer import MindObserver
from mind_prompts import MindPrompts
from mind_system import MindSystem
from mind_ultrathink import MindUltrathink
from portfolio_analyzer import PORTFOLIO_ANALYZER
from quant_signals import QuantConsensus
from questdb_adapter import QuestDBAdapter
from session_restorer import SessionRestorer
from shadow_sim import GhostShadowSim
from sovereign_decision_engine import SovereignDecisionEngine
from sovereign_task import TaskManager
from swarm_predictor import SwarmPredictor
from system_types import Position
from vault import Vault
from wisdom import SkillTreeManager, WisdomRepository
from workload_manager import WorkloadManager

if TYPE_CHECKING:
    import sqlite3

    from data_pipeline import DataPipeline
    from dhatu_oracle import DhatuOracle
    from dms import DMSMonitor
    from native_slm import NativeSLM

# DRAWDOWN LADDER


class DrawdownLevel(Enum):
    NORMAL = "NORMAL"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"
    CIRCUIT_BREAKER = "CIRCUIT_BREAKER"


@dataclass
class DrawdownLadder:
    """Tracks drawdown state for a specific account type."""

    account_type: str  # 'ibkr' or 'prop'
    peak_equity: float = 0.0
    current_equity: float = 0.0
    level: DrawdownLevel = DrawdownLevel.NORMAL
    cooldown_until: datetime | None = None

    # IBKR thresholds (personal account)
    IBKR_THRESHOLDS = {
        DrawdownLevel.NORMAL: 0.07,
        DrawdownLevel.YELLOW: 0.12,
        DrawdownLevel.ORANGE: 0.18,
        DrawdownLevel.RED: 0.25,
    }

    # Prop firm thresholds (FTMO)
    PROP_THRESHOLDS = {
        DrawdownLevel.NORMAL: 0.03,
        DrawdownLevel.YELLOW: 0.05,
        DrawdownLevel.ORANGE: 0.07,
        DrawdownLevel.RED: 0.09,
    }

    def update(self, equity: float) -> DrawdownLevel:
        """Update drawdown state and return current level."""
        if self.peak_equity == 0:
            logger.info(f"DrawdownLadder ({self.account_type}): Calibrating peak to ${equity:,.2f}")
            self.peak_equity = equity

        self.current_equity = equity
        self.peak_equity = max(self.peak_equity, equity)

        if self.peak_equity <= 0:
            return DrawdownLevel.NORMAL

        dd_pct = (self.peak_equity - equity) / self.peak_equity
        thresholds = self.PROP_THRESHOLDS if self.account_type == "prop" else self.IBKR_THRESHOLDS

        old_level = self.level

        if dd_pct >= thresholds[DrawdownLevel.RED]:
            self.level = DrawdownLevel.RED
        elif dd_pct >= thresholds[DrawdownLevel.ORANGE]:
            self.level = DrawdownLevel.ORANGE
        elif dd_pct >= thresholds[DrawdownLevel.YELLOW]:
            self.level = DrawdownLevel.YELLOW
        else:
            self.level = DrawdownLevel.NORMAL

        if self.level != old_level:
            logger.warning(
                f"Drawdown ladder [{self.account_type}]: {old_level.name} -> {self.level.name} "
                f"(DD: {dd_pct:.2%}, Peak: ${self.peak_equity:.2f}, Current: ${equity:.2f})"
            )
            from trading_state import TradingStateManager

            if self.level == DrawdownLevel.RED:
                TradingStateManager.halt(f"Drawdown Ladder [{self.account_type}] reached RED-ZONE.")
            elif self.level in (DrawdownLevel.YELLOW, DrawdownLevel.ORANGE):
                TradingStateManager.reduce_only(
                    f"Drawdown Ladder [{self.account_type}] escalation: {self.level.name}"
                )
            elif self.level == DrawdownLevel.NORMAL:
                TradingStateManager.activate(
                    f"Drawdown Ladder [{self.account_type}] recovered to NORMAL."
                )

        return self.level

    def get_size_modifier(self) -> float:
        """Return position size modifier based on tapered risk profile."""
        modifiers = {
            DrawdownLevel.NORMAL: 1.0,
            DrawdownLevel.YELLOW: 0.50,  # 50% Reduction
            DrawdownLevel.ORANGE: 0.25,  # 75% Reduction
            DrawdownLevel.RED: 0.10,  # 90% Reduction (Capital Preservation)
            DrawdownLevel.CIRCUIT_BREAKER: 0.0,
        }
        return modifiers.get(self.level, 0.0)

    def is_trading_allowed(self) -> bool:
        """Check if trading is permitted (Overridden for Sovereign Strike)."""
        if self.level == DrawdownLevel.CIRCUIT_BREAKER:
            return False
        # Red/Orange levels no longer block trading—they tighten the filter.
        return True


# CONSECUTIVE LOSS ESCALATION


@dataclass
class ConsecutiveLossTracker:
    """
    Graduated response:
    2 losses -> 50% size reduction
    3 losses -> 25% size + 1h pause
    4 losses -> paper mode
    5+ losses -> paper + audit required
    """

    consecutive_losses: int = 0
    win_streak: int = 0  # NEW: Breakthrough compounding tracker
    paper_mode_forced: bool = False
    audit_required: bool = False
    pause_until: datetime | None = None
    last_loss_time: datetime | None = None

    def _apply_time_decay(self) -> None:
        """Automatically recover 1 loss every 4 hours of inactivity."""
        if self.consecutive_losses <= 0 or not self.last_loss_time:
            return

        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_loss_time).total_seconds() / 3600

        # Recover 1 loss for every 4 hours
        recovered = int(elapsed // 4)
        if recovered > 0:
            old_losses = self.consecutive_losses
            self.consecutive_losses = max(0, self.consecutive_losses - recovered)
            if self.consecutive_losses < 4:
                self.paper_mode_forced = False
            if self.consecutive_losses < old_losses:
                logger.info(
                    f" RECOVERY: System regained {recovered} loss units via Time-Decay. "
                    f"Current: {self.consecutive_losses}"
                )
                self.last_loss_time = now - timedelta(
                    hours=(elapsed % 4)
                )  # Reset clock for next unit

    def _check_daily_reset(self) -> None:
        """Hard reset loss streak if it's a new trading day (after 8 AM ET)."""
        tz = pytz.timezone("US/Eastern")
        now = datetime.now(tz)
        # Check if we've crossed the 8 AM ET boundary
        if self.last_loss_time:
            # Convert last_loss_time to ET for comparison
            last_loss_et = self.last_loss_time.astimezone(tz)
            if last_loss_et.date() < now.date() and now.hour >= 8:
                if self.consecutive_losses > 0:
                    logger.info(
                        " MORNING RESET: Clearing previous session's loss streak for a fresh start."
                    )
                    self.consecutive_losses = 0
                    self.win_streak = 0
                    self.paper_mode_forced = False
                    self.audit_required = False
                    self.pause_until = None
                    self.last_loss_time = None

    def record_outcome(self, is_win: bool) -> None:
        """Record a trade outcome and update escalation state."""
        self._apply_time_decay()
        self._check_daily_reset()
        if is_win:
            self.consecutive_losses = 0
            self.win_streak += 1  # NEW: Win streak tracking
            self.paper_mode_forced = False
            self.audit_required = False
            self.pause_until = None
            if self.win_streak >= 3:
                logger.info(
                    f" VELOCITY REACHED: {self.win_streak} consecutive wins — "
                    "Compounding Risk Mode Active"
                )
        else:
            self.win_streak = 0
            self.consecutive_losses += 1
            self.last_loss_time = datetime.now(timezone.utc)
            if self.consecutive_losses >= 5:
                self.paper_mode_forced = True
                self.audit_required = True
                logger.critical(
                    f"G1 LEVEL 5: {self.consecutive_losses} consecutive losses — "
                    "PAPER MODE + AUDIT REQUIRED"
                )
            elif self.consecutive_losses >= 4:
                self.paper_mode_forced = True
                logger.error(
                    f"G1 LEVEL 4: {self.consecutive_losses} consecutive losses — FORCED PAPER MODE"
                )
            elif self.consecutive_losses >= 3:
                self.pause_until = datetime.now(timezone.utc) + timedelta(hours=1)
                logger.warning(
                    f"G1 LEVEL 3: {self.consecutive_losses} consecutive losses — "
                    "25% size + 1h pause"
                )
            elif self.consecutive_losses >= 2:
                logger.warning(
                    f"G1 LEVEL 2: {self.consecutive_losses} consecutive losses — 50% size reduction"
                )

    def get_size_modifier(self) -> float:
        """Return position size modifier based on consecutive wins/losses."""
        self._apply_time_decay()
        self._check_daily_reset()

        if self.consecutive_losses >= 4:
            return 0.0  # Paper mode — no real trades
        elif self.consecutive_losses >= 3:
            return 0.25
        elif self.consecutive_losses >= 2:
            return 0.50

        if self.win_streak >= 3:
            # 1.2x for streak 3, 1.4x for streak 4, up to 2.0x cap
            multiplier = 1.0 + (min(self.win_streak, 8) - 3) * 0.2
            return min(float(multiplier), 2.0)

        return 1.0

    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed (not paused/paper)."""
        if self.paper_mode_forced:
            return False
        pause = self.pause_until
        if pause and datetime.now(timezone.utc) < pause:
            return False
        return True


# TRADING STATE MACHINE


class TradingState(Enum):
    STANDBY = 1
    SCANNING = 2
    ANALYZING = 3
    POSITIONED = 4
    EXIT = 5


# Position class removed (Transferred to src/types.py for Coordinator-Safe Inversion)


# MORNING RISK BUDGET


@dataclass
class MorningBudget:
    """Daily risk budget set by Agent A at 8 AM ET."""

    max_trades: int = 2
    min_catalyst: int = 70
    max_risk_per_trade_pct: float = 0.02
    max_daily_risk_pct: float = 0.04
    regime: str = "UNKNOWN"
    generated_at: datetime | None = None

    def generate(
        self,
        regime: str,
        consecutive_losses: int,
        dd_level: DrawdownLevel,
        breadth_score: float = 50.0,
        fomc_proximity_days: int = 30,
    ) -> None:
        """Generate morning budget based on current conditions."""
        self.regime = regime
        self.generated_at = datetime.now(timezone.utc)

        # Base config by regime
        regime_config = {
            "BULL": {"max_trades": 20, "min_catalyst": 55, "risk_pct": 0.02},
            "TRENDING": {"max_trades": 15, "min_catalyst": 58, "risk_pct": 0.018},
            "CHOPPY": {"max_trades": 10, "min_catalyst": 58, "risk_pct": 0.015},
            "VOLATILE": {"max_trades": 10, "min_catalyst": 60, "risk_pct": 0.01},
            "BEAR": {"max_trades": 8, "min_catalyst": 58, "risk_pct": 0.005},
        }

        config = regime_config.get(regime, regime_config["CHOPPY"])
        self.max_trades = int(config["max_trades"])
        self.min_catalyst = int(config["min_catalyst"])
        self.max_risk_per_trade_pct = float(config["risk_pct"])

        # Consecutive loss modifier
        if consecutive_losses >= 3:
            self.max_trades = min(self.max_trades, 1)
            self.min_catalyst += 10
        elif consecutive_losses >= 2:
            self.min_catalyst += 5

        # Drawdown modifier
        if dd_level in (DrawdownLevel.ORANGE, DrawdownLevel.RED):
            self.max_trades = 0
        elif dd_level == DrawdownLevel.YELLOW:
            self.max_trades = min(self.max_trades, 1)
            self.min_catalyst += 5

        # FOMC proximity (within 2 days)
        if fomc_proximity_days <= 2:
            self.max_trades = min(self.max_trades, 1)
            self.min_catalyst += 10

        # Low breadth modifier
        if breadth_score < 40:
            self.min_catalyst += 5

        # Broker-specific max trade cap (IBKR paper/live is not FTMO constrained)
        self.max_trades = min(self.max_trades, IBKR_MAX_TRADES_PER_DAY)

        logger.info(
            f"Morning Budget: regime={regime} max_trades={self.max_trades} "
            f"min_catalyst={self.min_catalyst} max_risk={self.max_risk_per_trade_pct:.2%}"
        )


# RATE LIMITER (IBKR Protection)


class TokenBucketRateLimiter:
    """
    Asynchronous Token Bucket for IBKR 50 msgs/sec limit protection.
    Caps order routing to a safe burst frequency.
    """

    def __init__(self, rate: float, capacity: int) -> None:
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        while True:
            async with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.tokens = min(float(self.capacity), self.tokens + elapsed * self.rate)
                self.last_update = now

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                # Calculate wait time for the next token
            await asyncio.sleep(0.01)


# THE TRADING BRAIN


class TradingBrain:
    """
    The Central Orchestrator of the Sovereign Trading System.
    Responsibilities:
    - Synchronizing the 7 Master Minds (Agents A-G) via the MindBridge.
    - Orchestrating the 20Hz (BRAIN_SCAN_INTERVAL) internal pulse.
    - Managing global state, regime shifts, and risk invariants.
    - Executing the 'Phantom Probe' system wiring checks.
    Main orchestrator for the trading system.
    Manages state transitions, agent orchestration, position monitoring,
    drawdown ladders, consecutive loss tracking, and morning risk budget
    """

    async def transition_to(self, new_state: TradingState) -> None:
        """
        Ensures state changes are logged, validated, and published.
        """
        async with self._state_lock:
            old_state = getattr(self, "state", TradingState.STANDBY)
            if old_state == new_state:
                return

            self.state = new_state
            logger.info(f" BRAIN STATE TRANSITION: {old_state.name} ➔ {new_state.name}")

            await self._safe_publish(
                "system.state",
                {
                    "old": old_state.name,
                    "new": new_state.name,
                    "timestamp": time.time_ns(),
                },
            )

    async def _safe_publish(self, topic: str, payload: Any) -> bool:
        """Publish safely to the shared intelligence bus if available and valid."""
        if self.bus is None:
            logger.debug(f"Bus unavailable, dropping publish: {topic}")
            return False

        publish_method = getattr(self.bus, "publish", None)
        if publish_method is None or not callable(publish_method):
            logger.warning(
                f"Invalid bus.publish callable for topic '{topic}'. "
                f"Bus type: {type(self.bus).__name__}"
            )
            return False

        try:
            await publish_method(topic, payload)
            return True
        except Exception as exc:
            logger.warning(f"Safe publish failed for topic '{topic}': {exc}", exc_info=True)
            return False

    def __init__(
        self,
        db_conn: Optional["sqlite3.Connection"] = None,
        ibkr_client: Optional[Any] = None,
        mt5_client: Optional[Any] = None,
        dms: Optional[Any] = None,
        mode: str = "paper",
        dhatu_oracle: Optional["DhatuOracle"] = None,
        qdb: Optional["QuestDBAdapter"] = None,
        swarm_predictor: Optional["SwarmPredictor"] = None,
        bus: Optional["SharedIntelligenceBus"] = None,
        native_slm: Optional["NativeSLM"] = None,
    ) -> None:
        logger.info(" TradingBrain: Initializing constructor...")
        self.db_conn = db_conn
        self.ibkr_client = ibkr_client
        self.mt5_client = mt5_client
        self.dms = dms
        # SharedIntelligenceBus — the nervous system connecting all agents
        self.bus: SharedIntelligenceBus | None = bus
        if self.bus is not None and not isinstance(self.bus, SharedIntelligenceBus):
            logger.warning(
                "TradingBrain: invalid bus injected (%s); disabling bus publishing.",
                type(self.bus).__name__,
            )
            self.bus = None
        self.native_slm = native_slm
        self.dhatu_oracle = dhatu_oracle
        self.emergency_halted = False
        self._state_lock = asyncio.Lock()
        self.state = TradingState.STANDBY
        self.last_tick_prices: dict[str, float] = {}
        self.last_tick_bids: dict[str, float] = {}
        self.last_tick_asks: dict[str, float] = {}
        self._last_tick_price: dict[str, float] = {}  # Internal shadow for snapshotting
        self._last_tick_time: dict[str, datetime] = {}
        self.new_tick_event = asyncio.Event()
        # SPY Momentum Buffer (stores last 200 prices for zero-latency regime detection)

        from collections import deque

        self.spy_buffer = deque(maxlen=200)

        # Mode selection — respects FORCED_PAPER_MODE safety lock from config.
        # Modes:
        #   "paper"      — fully local simulation, NO broker connection
        #   "ibkr_paper" — routes REAL orders to IBKR paper trading account via TWS/Gateway
        #   "live"       — routes REAL orders to IBKR live account (ONLY when authorized)
        if FORCED_PAPER_MODE and mode not in ("paper",):
            logger.warning(
                f"FORCED_PAPER_MODE is active — overriding requested mode '{mode}' to 'paper'. "
                "Set FORCED_PAPER_MODE=False in src/config.py to enable IBKR execution."
            )
            self.mode = "paper"
        else:
            self.mode = mode

        # 3. Environment Sanitization & Matrix Scents
        self._oracle_risk_modifier: float = 1.0
        self._oracle_dhatu: str = "Sthiti"
        self._oracle_freeze: bool = False

        if self.dhatu_oracle:
            initial_state = self.dhatu_oracle.get_current_state()
            if initial_state and initial_state.is_fresh:
                self._oracle_risk_modifier = float(initial_state.risk_modifier)
                self._oracle_dhatu = str(initial_state.dhatu_state)
                self._oracle_freeze = self._oracle_dhatu in ("Abhava", "Viyoga")
                logger.info(
                    f"TradingBrain: Initialized with recovered Oracle state: {self._oracle_dhatu} "
                    f"(Modifier: {self._oracle_risk_modifier:.2f}, Freezed: {self._oracle_freeze})"
                )

        self._last_reconciliation = 0.0

        # Updated via calibration.update events from Agent D's LiveLearningEngine
        # key: "PATTERN|REGIME|SESSION" -> win_rate (0.0 to 1.0)
        self._learned_win_rates: dict[str, float] = {}

        # Shared QuestDB adapter (injected from TradingSystem) avoids duplicate probes
        self.qdb = qdb if qdb is not None else QuestDBAdapter(enabled=QUESTDB_ENABLED)

        # MiroFish swarm intelligence predictor (optional)
        self.swarm_predictor: SwarmPredictor | None = swarm_predictor

        # Store dhatu_oracle reference BEFORE Agent B init (which references it)
        self.dhatu_oracle = dhatu_oracle

        logger.info("Initializing TradingBrain components...")
        self.positions: list[Position] = []
        self.closed_positions: collections.deque = collections.deque(
            maxlen=500
        )  # Memory-bounded history
        self.pending_signals: list[dict] = []
        self._state_lock = asyncio.Lock()
        self.rate_limiter = TokenBucketRateLimiter(
            rate=20.0, capacity=20
        )  # 20 orders/sec max burst
        self.session_pnl = 0.0
        self.session_stats = {"scanned": 0, "detected": 0, "approved": 0, "rejected": 0}

        self.budget_monitor = ContinuousBudgetMonitor()
        self.pattern_detector = PatternDetector()
        self.entropy_calc = SignalEntropyCalculator()
        self.escape_classifier = EscapeVelocityClassifier()
        self.mtf_aligner = MultiTimeframeAligner()
        self.sovereign_atlas = InMemorySovereignAtlas()
        self.neural_engine = FactorWeightCalibration()
        self.regime_classifier_neural = NeuralRegimeClassifier()

        self.dhatu_classifier = DhatuClassifier(oracle=self.dhatu_oracle)
        self.belief_tracker = BayesianBeliefTracker(prior=0.50)
        self.abhava_detector = ABHAVADetector()

        self.ibkr_conn = IBKRConnection(ibkr_client)
        self.ibkr_conn.brain = self
        self.ibkr_sizer = PositionSizingChain()
        self.vix_protocol = VIXProtocol()
        self.cascade_checker = CorrelationCascade()
        self.blackswan = BlackSwanProtocol()
        self.portfolio_guard = PortfolioGuard()

        from agent_c_mt5 import MT5Connection, MT5PositionSizer

        self.mt5_conn = MT5Connection()
        self.mt5_sizer = MT5PositionSizer()
        self.active_broker = (Vault.get("ACTIVE_BROKER") or "IBKR").upper()
        logger.info(f"MindBrain: Active Broker target set to [{self.active_broker}]")

        self.regime_classifier = RegimeClassifier()
        self.stat_gate = StatisticalSignificanceGate()
        self.crowding_detector = EdgeCrowdingDetector()
        self.entropy_monitor = SystemEntropyMonitor()
        self.recursive_evolution = LiveRecursiveEvolution(atlas=self.sovereign_atlas)

        # 4. Live Learning Engine — Agent D persistent matrix, subscribed to trade.exit
        _db_path = "data/trading.db"
        self.db_path = _db_path  # Needed by session_restorer.restore_peak_equity
        self.live_learner = LiveLearningEngine(
            db_path=_db_path, bus=bus, evolution_engine=self.recursive_evolution, dms=self.dms
        )

        self._qdb_circuit_broken = False
        self._qdb_last_failure_time = 0.0
        self._qdb_failure_count = 0
        self._hot_cache: dict[str, pd.DataFrame] = {}  # symbol -> OHLCV df
        self._hot_cache_time: dict[str, float] = {}  # symbol -> monotonic ts

        self.exit_engine = ExitIntelligence({"belief_threshold": 0.35})
        self._exit_failure_counts: dict[str, int] = {}

        self.ibkr_drawdown = DrawdownLadder(account_type="ibkr", peak_equity=STARTING_CAPITAL_CAD)
        self.prop_drawdown = DrawdownLadder(account_type="prop", peak_equity=STARTING_CAPITAL_CAD)
        self.correlation_guard = CorrelationGuard(max_sector_exposure=0.30)
        self.loss_tracker = ConsecutiveLossTracker()
        self.morning_budget = MorningBudget()
        self.last_budget_date: datetime | None = None

        self.swarm_predictor = swarm_predictor
        self.bus = bus

        self.wisdom = WisdomRepository()
        self.skill_tree = SkillTreeManager()
        self.wisdom_context = "SYSTEM_WARMUP: Wisdom hydration in progress..."

        self.session_restorer = SessionRestorer()
        self.macros = MindMacros()
        self.mission_manager = WorkloadManager()  # Unified Mission Board
        self.memory_manager = MemoryManager()
        self.mind_prompts = MindPrompts(memory=self.memory_manager)

        # SEED WITH PLACEHOLDER (Will be updated via async update_wisdom_context)
        initial_context = f"""
        MISSION: {self.mission_manager.current_mission}
        STATUS: HYDRATING_WISDOM_DEFERRED
        """
        self.bridge = MindBridge(bus=bus, initial_context=initial_context)

        self.mind_architect = MindArchitect(bridge=self.bridge, vault=Vault())
        self.mind_evolution = MindEvolution(bridge=self.bridge)
        self.mind_observer = MindObserver(bridge=self.bridge, qdb=self.qdb)
        self.mind_experiment = MindExperiment(bridge=self.bridge)
        self.mind_ultrathink = MindUltrathink(bridge=self.bridge)
        self.mind_system = MindSystem(bridge=self.bridge)
        self.mind_ghost = MindGhost(bridge=self.bridge)
        self.mind_math = MindMath(bridge=self.bridge)

        self._quant_consensus = QuantConsensus()
        self._quant_fitted = False

        from coordinator import TradingCoordinator

        self.coordinator = TradingCoordinator(self.bridge, self)
        self.task_manager = TaskManager()

        self.current_regime = "UNKNOWN"
        self.is_running = False
        self.conviction_state = {}

        is_mock_db = type(self.db_conn).__module__.startswith("unittest.mock")
        capsule = None if is_mock_db else self.session_restorer.load_cognitive_capsule()
        if capsule:
            self.current_regime = capsule.get("regime", "UNKNOWN")
            self.conviction_state = capsule.get("conviction_state", {})
            self.session_pnl = capsule.get("session_pnl", 0.0)
            logger.info(
                f"Brain: Cognitive Capsule inhaled. Regime: {self.current_regime} | "
                f"PnL: ${self.session_pnl:.2f}"
            )

        self.conviction_state = {
            "Dhatu_Oracle": {
                "agent": "Dhatu_Oracle",
                "vote": "YES",
                "confidence": 0.5,
                "reason": "Initializing",
                "timestamp": time.time_ns(),
            },
            "Swarm_Predictor": {
                "agent": "Swarm_Predictor",
                "vote": "YES",
                "confidence": 0.5,
                "reason": "Initializing",
                "timestamp": time.time_ns(),
            },
            "Mind_Ultrathink": {
                "agent": "Mind_Ultrathink",
                "vote": "YES",
                "confidence": 0.5,
                "reason": "Initializing",
                "timestamp": time.time_ns(),
            },
        }

        # Legacy aliases for backward compatibility (Fixes TraderMind Error)
        self.mind_bridge = self.bridge
        self._last_account_value = {"ibkr": 0.0, "mt5": 0.0, "timestamp": 0.0}

        # This MUST be done before agents start or they will fail to find these tools.
        self.bridge.register_tool("get_account_status", self._tool_get_account_status)
        self.bridge.register_tool("get_open_positions", self._tool_get_open_positions)

        self.last_scan_stats = {
            "cycle": 0,
            "watchlist": 0,
            "scanned": 0,
            "no_data": 0,
            "stale": 0,
            "too_short": 0,
            "patterns_detected": 0,
            "patterns_approved": 0,
            "patterns_rejected": 0,
            "pending": 0,
            "regime": "UNKNOWN",
        }

        self.decision_engine = SovereignDecisionEngine(bus=self.bus)

        self.state = TradingState.STANDBY

        # current_regime already set via capsule
        self.last_regime_update: datetime | None = None  # Tracking for periodic refresh
        from config import BRAIN_SCAN_INTERVAL

        self.scan_interval = BRAIN_SCAN_INTERVAL  # Configurable SETO Pulse
        self.MAX_ORDER_VALUE_USD = 50000.0
        self.evolution_manager = EvolutionManager(
            main_db_path=self.db_path, dms=self.dms
        )  # Agent C's learning engine
        self.evolution_manager.load_optimizations()

        # Only initialize if MT5 login exists and is not a placeholder
        _ml = Vault.get("MT5_LOGIN")

        if _ml and "YOUR_MT5" not in str(_ml).upper() and str(_ml).lower() != "none":
            from agent_c_mt5 import FTMOComplianceLayer, MT5PositionSizer

            self.ftmo_compliance = FTMOComplianceLayer()
            self.mt5_sizer = MT5PositionSizer()
            logger.info("MindBrain: MT5 Cognitive Layer ENGAGED (Institutional Mode).")
        else:
            self.ftmo_compliance = None
            self.mt5_sizer = None
            logger.info("MindBrain: MT5 Cognitive Layer DISABLED (Resources Recovered).")

        # Event sync for Intelligence Bus (candle.batch wakes the scanner)
        self.new_candle_event = asyncio.Event()
        self.safe_mode = False

        # Dedicated Watchdog Background Task (Decouples heartbeats from processing state)
        self._watchdog_task: asyncio.Task | None = None

        # Dedicated Monitoring Task
        self._monitoring_task: asyncio.Task | None = None

        # Scan-cycle diagnostics — persisted so the API can read them at any time
        self._scan_cycle: int = 0
        self.last_scan_time: datetime | None = None
        self._vetting_cooldowns: dict[str, datetime] = {}  # Symbol -> last vet time

        self._exit_failure_count: dict[str, int] = {}  # Symbol -> Strike Count
        self._exit_last_attempt: dict[str, datetime] = {}  # Symbol -> Last Re-attempt
        self._order_submit_times: dict[int, datetime] = {}  # OrderId -> Submission time

        # Check if we have a persisted state to recover from after a crash
        # Dispatched as a background task to prevent blocking the boot dashboard
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._thaw_task = None
        else:
            self._thaw_task = loop.create_task(self._thaw_session_async())

    async def _thaw_session_async(self) -> None:
        """Restores the brain's state via background thread to prevent startup hangs."""
        try:
            state = await asyncio.to_thread(self.session_restorer.thaw_state)
            if state:
                # Restore positions with FORCE HYDRATION (Pillar 2 Hardening)
                thawed_pos = state.get("positions", [])
                self.positions = []
                for p_data in thawed_pos:
                    if isinstance(p_data, Position):
                        self.positions.append(p_data)
                    elif isinstance(p_data, dict) and "symbol" in p_data:
                        try:
                            # Safely reconstruct Position from legacy dict
                            from dataclasses import fields

                            valid_keys = {f.name for f in fields(Position)}
                            filtered_data = {k: v for k, v in p_data.items() if k in valid_keys}
                            self.positions.append(Position(**filtered_data))
                        except Exception as _pos_err:
                            logger.debug(
                                f"Brain: Skipping malformed position state entry: {_pos_err}"
                            )

                self.ibkr_drawdown.peak_equity = state.get(
                    "peak_equity", self.ibkr_drawdown.peak_equity
                )
                if "loss_tracker" in state:
                    lt_state = state["loss_tracker"]
                    self.loss_tracker.consecutive_losses = lt_state.get("consecutive_losses", 0)
                    self.loss_tracker.win_streak = lt_state.get("win_streak", 0)
                    if "last_loss_time" in lt_state and lt_state["last_loss_time"]:
                        try:
                            self.loss_tracker.last_loss_time = datetime.fromisoformat(
                                lt_state["last_loss_time"]
                            )
                        except Exception as _dt_err:
                            logger.debug(f"Brain: Skipping bad last_loss_time format: {_dt_err}")

                logger.info(
                    "MindBrain: Legacy state thawed in background. "
                    f"{len(self.positions)} positions restored."
                )
        except Exception as e:
            logger.error(f"MindBrain: Background thaw failure: {e}")

        # Always restore peak_equity from DB (survives even if .session.bin is missing)
        try:
            await asyncio.to_thread(
                self.session_restorer.restore_peak_equity, self.db_path, self.ibkr_drawdown
            )
        except Exception as _sr_err:
            logger.debug(f"Brain: Non-critical session restore error (continuing): {_sr_err}")

    async def quant_gate(self, symbol: str, side: str, market_data: dict) -> dict:
        """Returns {'approved': bool, 'reason': str, 'consensus': dict}"""
        prices = np.array(market_data.get("prices", []))
        volumes = np.array(market_data.get("volumes", []))

        if len(prices) < 30:
            return {"approved": True, "reason": "insufficient_data_for_quant", "consensus": {}}

        # Fit on first call
        if not self._quant_fitted and len(prices) >= 200:
            self._quant_consensus.fit(prices)
            self._quant_fitted = True

        closed = list(self.closed_positions)
        win_rate = 0.5
        avg_win = avg_loss = 1.0
        if closed:
            pnls = [getattr(p, "realized_pnl", getattr(p, "net_pnl", 0)) for p in closed[-50:]]
            wins = [p for p in pnls if p > 0]
            losses = [abs(p) for p in pnls if p <= 0]
            win_rate = len(wins) / (len(pnls) + 1e-10)
            avg_win = float(np.mean(wins)) if wins else 1.0
            avg_loss = float(np.mean(losses)) if losses else 1.0

        # Use DrawdownLadder peak_equity (the most accurate live account value)
        portfolio_value = float(
            self.ibkr_drawdown.peak_equity or self._last_account_value.get("ibkr", 500.0)
        )

        consensus = self._quant_consensus.evaluate(
            symbol,
            prices,
            volumes,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            portfolio_value=float(portfolio_value),
        )

        # Veto logic: if quant strongly disagrees with requested side, block
        quant_phase = consensus["phase"]
        regime_veto = consensus["regime_veto"]

        opposite = (side == "LONG" and quant_phase == "SELL") or (
            side == "SHORT" and quant_phase == "BUY"
        )

        if regime_veto:
            return {"approved": False, "reason": "quant_regime_veto", "consensus": consensus}
        if opposite and consensus["confidence"] > 0.8:
            return {
                "approved": False,
                "reason": f"quant_opposing_{quant_phase}",
                "consensus": consensus,
            }

        # Approved — enrich with Kelly sizing
        return {
            "approved": True,
            "reason": "quant_approved",
            "consensus": consensus,
            "kelly_position": consensus.get("position_usd", 0),
            "kelly_fraction": consensus.get("kelly_fraction", 0),
        }

    async def get_ibkr_cushion(self) -> float:
        """Proxy to Agent C's margin probe."""
        if hasattr(self.coordinator, "agents") and "agent_c_ibkr" in self.coordinator.agents:
            # Type check before calling
            agent = self.coordinator.agents["agent_c_ibkr"]
            if hasattr(agent, "get_margin_cushion"):
                return agent.get_margin_cushion()
        return 1.0  # Default to safe

    async def _on_hft_tick(self, payload: dict) -> None:
        """Cache incoming ticks for high-frequency pricing updates."""
        symbol = payload.get("symbol")
        price = payload.get("price")
        if symbol and price:
            self.last_tick_prices[symbol] = float(price)

    async def _on_hft_news(self, payload: dict) -> None:
        """Neural News Trigger: Triggers re-scans on high-impact headlines."""
        headline = str(payload.get("headline", "")).upper()
        sentiment = float(payload.get("sentiment", 0.0))
        impact = float(payload.get("impact", 0.0))

        # The Scent: Keywords that move the world
        IMPACT_KEYWORDS = [
            "FED",
            "CPI",
            "FOMC",
            "POWELL",
            "INFLATION",
            "RATE",
            "CRASH",
            "WAR",
            "HALT",
            "TREASURY",
        ]
        is_hft_impact = any(k in headline for k in IMPACT_KEYWORDS) or impact > 0.6

        if is_hft_impact:
            logger.info(
                f" BRAIN: News Action Triggered -> {headline[:60]}... "
                f"(Sent: {sentiment:.2f}, Imp: {impact:.2f})"
            )

            # Apply Neural Bias to the next scan cycle
            # Base risk is set by oracle; news provides a transient ±15% shift.
            if sentiment != 0.0:
                shift_size = sentiment * 0.15
                target_modifier = self._oracle_risk_modifier * (1.0 + shift_size)
                # Sane bounds
                self._oracle_risk_modifier = max(0.5, min(1.8, target_modifier))
                logger.info(
                    " BRAIN: News-Driven Risk Shift active "
                    f"(Transient Modifier: {self._oracle_risk_modifier:.2f})"
                )

            # Force an immediate scan of the watchlist
            self.new_candle_event.set()

    async def _decay_risk_modifier(self):
        """Gradually decays the oracle risk modifier back towards baseline (Oracle State)."""
        if not self.dhatu_oracle:
            return

        current_state = self.dhatu_oracle.get_current_state()
        if not current_state:
            return

        baseline = float(current_state.risk_modifier)

        if abs(self._oracle_risk_modifier - baseline) > 0.01:
            # 5% closure per cycle towards baseline
            diff = baseline - self._oracle_risk_modifier
            self._oracle_risk_modifier += diff * 0.05
            if abs(self._oracle_risk_modifier - baseline) < 0.01:
                self._oracle_risk_modifier = baseline
            logger.debug(f"Risk Decay: {self._oracle_risk_modifier:.4f} -> {baseline}")

    # MAIN LOOP

    async def start(self) -> None:
        """Start the trading brain as a background task."""
        self.is_running = True
        logger.info(f"Trading Brain started in {self.mode} mode.")

        from config import PANIC_LIQUIDATE

        if PANIC_LIQUIDATE:
            logger.critical(" PANIC SWITCH DETECTED: Initiating Total Portfolio Liquidation...")
            await self._panic_liquidate_all()
            # We do NOT exit, we allow the brain to continue in a clean state.

        # Initialize bayesian prior
        self.belief_tracker.reset(0.50)

        await self._restore_positions_from_db()

        # Launch loops/tasks
        self._bus_task = asyncio.create_task(self._run_bus_listener())
        self._learner_task = asyncio.create_task(self.live_learner.run())
        self._watchdog_task = asyncio.create_task(self._run_watchdog())
        self._evolution_task = asyncio.create_task(self.evolution_manager.run_evolution_cycle())
        self._main_task = asyncio.create_task(self._run_loop())

        # Launch Matrix Logic-Stream
        logger.info("TradingBrain: Waking up The Infinity Matrix...")

        previous_state = self.session_restorer.thaw_state()
        if previous_state:
            # Restore thresholds, win rates, and cognitive mission board
            self._learned_win_rates = previous_state.get("win_rates", {})
            self.session_stats = previous_state.get("session_stats", self.session_stats)
            if hasattr(self, "trading_brain"):
                self.trading_brain.session_pnl = previous_state.get("session_pnl", 0.0)
            logger.info("TradingBrain: Quantum Thaw SUCCESS — System state restored.")

        await self.mind_architect.start()
        await self.mind_evolution.start()
        await self.mind_observer.start()
        await self.mind_experiment.start()
        await self.mind_ultrathink.start()
        await self.mind_system.start()
        await self.mind_ghost.start()  # Launch Agent J

        # Update mission board context
        await self.mission_manager.update_mission(
            "Generate Unlimited Cash",
            [
                "Audit IBKR Latency",
                "Verify QuestDB Consistency",
                "Detect High-Vola Regimes",
                "Optimize R:R Ratios",
            ],
        )

        # Update session memory on start
        self.memory_manager.update_session_memory(
            f"- INFINITY MATRIX ONLINE: {time.time_ns()}\n", mode="a"
        )

        self._mind_task = asyncio.create_task(self._run_trader_mind())

        # Detects wiring disconnects by running non-destructive trial trades.
        self._phantom_probe_task = asyncio.create_task(self._run_phantom_probe())

        self._conviction_task = asyncio.create_task(self._background_conviction_sync())

        # Background task for periodic freezing (Safety gate)
        self._freezer_task = asyncio.create_task(self._run_periodic_freeze())

        logger.info("TradingBrain: All Matrix background minds launched (Absolute 100% Logic).")

    async def run(self) -> None:
        """Entry point for supervisor — blocks until tasks are finished."""
        logger.info(" MAIN BRAIN TASK ACTIVATED")
        await self.start()

        # Ensures the Brain never exits unexpectedly after a Veto or Rejection.
        try:
            while self.is_running:
                # Wait for critical background minds
                # We await the main_loop task specifically as it's the heartbeat
                if hasattr(self, "_main_task") and self._main_task:
                    await asyncio.shield(self._main_task)

                # If we get here, the main task finished or errored.
                # If is_running is still True, we must restart.
                if self.is_running:
                    logger.warning(
                        "TradingBrain: Main task exited prematurely. Restarting cycle..."
                    )
                    self._main_task = asyncio.create_task(self._run_loop())
                    await asyncio.sleep(5)
                else:
                    break

        except asyncio.CancelledError:
            logger.info("TradingBrain: Run task cancelled.")
            await self.stop()
            raise
        except Exception as e:
            logger.error(f"TradingBrain: Systemic failure: {e}", exc_info=True)
            await self.stop()
            raise

    async def _run_loop(self) -> None:
        """The primary state machine loop for the Trading Brain."""
        logger.info("TradingBrain: Main system loop started.")
        await asyncio.sleep(10)
        while self.is_running:
            try:
                # No internal error shall ever stop the Sovereign.
                try:
                    old_state = self.state

                    if self.dms:
                        self.dms.record_heartbeat()
                    if self.mind_ghost:
                        await self.mind_ghost.update_heartbeat("ENGINE")
                        if (
                            hasattr(self, "ibkr_client")
                            and self.ibkr_client
                            and self.ibkr_client.isConnected()
                        ):
                            await self.mind_ghost.update_heartbeat("IBKR")
                        if hasattr(self, "mt5_client") and self.mt5_client:
                            await self.mind_ghost.update_heartbeat("MT5")

                    if self.emergency_halted:
                        await self._handle_emergency()
                        continue

                    if self._scan_cycle % 50 == 0:
                        logger.info(
                            f"[SOVEREIGN] Pulse active. Cycle: #{self._scan_cycle} | "
                            f"State: {self.state.name}"
                        )

                    # Run Adoption/Pruning Protocol every 10 seconds across ALL states
                    if time.monotonic() - self._last_reconciliation > 10:
                        await self._reconcile_broker_positions()
                        self._last_reconciliation = time.monotonic()

                    if self.state == TradingState.STANDBY:
                        await self._state_standby()
                    elif self.state == TradingState.SCANNING:
                        await self._decay_risk_modifier()

                        if self.positions and (
                            self._monitoring_task is None or self._monitoring_task.done()
                        ):
                            self._monitoring_task = asyncio.create_task(self._state_positioned())

                        if self.bus and self._scan_cycle % 100 == 0:  # Only once every 100 cycles
                            await self.bus.publish(
                                "brain.warmup", {"symbols": ["SPY", "QQQ", "TSLA", "NVDA"]}
                            )

                        await self._state_scanning()
                    elif self.state == TradingState.ANALYZING:
                        await self._state_analyzing()
                    elif self.state == TradingState.POSITIONED:
                        self.state = TradingState.SCANNING
                        await asyncio.sleep(self.scan_interval)
                    elif self.state == TradingState.EXIT:
                        await self._state_exit()

                    if self.state != old_state and self.bus:
                        await self.bus.publish("system.state", {"state": self.state.name})

                except Exception as loop_e:
                    logger.error(
                        f"SSS-Tier Recovery: Loop anomaly detected: {loop_e}. "
                        "Forcing reset to SCANNING...",
                        exc_info=True,
                    )
                    async with self._state_lock:
                        self.state = TradingState.SCANNING
                    await asyncio.sleep(5)
                    continue

                await asyncio.sleep(self.scan_interval)

            except asyncio.CancelledError:
                logger.info("TradingBrain: System loop cancelled externally.")
                break
            except Exception as outer_e:
                logger.error(
                    f"Critical Systemic Friction: {outer_e}. Maintaining Heartbeat...",
                    exc_info=True,
                )
                from telegram_alerts import send_telegram_alert

                await send_telegram_alert(
                    " *SYSTEM CRITICAL ERROR*\n"
                    f"{outer_e}\nBrain is attempting autonomous healing..."
                )
                await asyncio.sleep(10)

                # Autonomous Healing Trigger
                error_trace = traceback.format_exc()
                await self.mind_bridge.broadcast(
                    "trader",
                    "SYSTEM CRITICAL: Main loop exception detected. "
                    f"Traceback: {error_trace[:500]}...",
                    {"type": "EXCEPTION", "traceback": error_trace},
                )
                await asyncio.sleep(5)

        logger.info("TradingBrain: Main system loop exited.")

    async def _run_periodic_freeze(self) -> None:
        """Periodically saves the cognitive state to the Quantum Session Restorer."""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Freeze state every 5 minutes
                state = {
                    "positions": self.positions,
                    "peak_equity": self.ibkr_drawdown.peak_equity,
                    "session_stats": self.session_stats,
                    "regime": self.current_regime,
                    "loss_tracker": {
                        "consecutive_losses": self.loss_tracker.consecutive_losses,
                        "win_streak": self.loss_tracker.win_streak,
                        "last_loss_time": self.loss_tracker.last_loss_time.isoformat()
                        if self.loss_tracker.last_loss_time
                        else None,
                    },
                    "timestamp": time.time_ns(),
                }
                await asyncio.to_thread(self.session_restorer.freeze_state, state)
            except Exception as e:
                logger.error(f"Periodic Freeze Error: {e}")
                await asyncio.sleep(10)

    async def _run_trader_mind(self) -> None:
        """
        Agent F: The Executioner's Cognitive Layer.
        Participates in SETO 'Twin-Mind' discussion and evolution.
        LLM Circuit Breaker: If get_next_message blocks for >8s, the mind
        is assumed unresponsive and the loop continues without it.
        """
        logger.info("TraderMind: Participation loop active.")
        while self.is_running:
            try:
                # Circuit breaker: never block the trading loop indefinitely
                # waiting for an LLM mind that may have timed out.
                try:
                    msg = await asyncio.wait_for(
                        self.mind_bridge.get_next_message("trader"), timeout=8.0
                    )
                except asyncio.TimeoutError:
                    # Queue is empty — no agent sent a message in 8s.
                    # This is NORMAL during idle periods and is NOT an LLM API failure.
                    # Do NOT record a circuit breaker failure here.
                    logger.debug("TraderMind: No messages in 8s (queue idle). Continuing loop.")
                    await asyncio.sleep(1)
                    continue

                # Trader logic to respond to architect's queries or suggestions
                if "heal" in msg.content.lower():
                    logger.info(
                        f"TraderMind: Architect is performing a healing procedure: {msg.content}"
                    )
                elif "evolution" in msg.content.lower():
                    # Potentially apply parameter updates suggested by Architect
                    logger.info("TraderMind: Evolution proposal received.")
            except Exception as e:
                logger.error(f"TraderMind Error: {e}")
                await asyncio.sleep(1)

    # INDEPENDENT WATCHDOG

    async def _run_watchdog(self) -> None:
        """
        Background task pulsing the DMS every 15 seconds and publishing
        live state to frontend.
        """
        logger.info("BrainWatchdog: Pulse task active (15s interval)")
        while self.is_running:
            try:
                if self.dms:
                    self.dms.record_heartbeat("BRAIN_PRIMARY")
                    self.dms.record_heartbeat("COORDINATOR")
                    self.dms.record_heartbeat("AGENT_A")
                    self.dms.record_heartbeat("AGENT_C")

                # Publish system.state to the bus every 15s so the frontend
                # stays live between WebSocket connect snapshots.
                if self.bus is not None:
                    try:
                        scan_stats = getattr(self, "last_scan_stats", {})
                        state_payload = {
                            "brain": {
                                "state": self.state.name if hasattr(self, "state") else "UNKNOWN",
                                "regime": getattr(self, "current_regime", "UNKNOWN"),
                                "positions_count": len(getattr(self, "positions", [])),
                                "pnl_session": self.session_pnl
                                + sum(
                                    getattr(p, "unrealized_pnl", 0.0)
                                    for p in getattr(self, "positions", [])
                                ),
                                "scan_stats": scan_stats,
                                "consecutive_losses": getattr(
                                    getattr(self, "loss_tracker", None), "consecutive_losses", 0
                                ),
                                "oracle_dhatu": getattr(self, "_oracle_dhatu", "NEUTRAL"),
                                "oracle_freeze": getattr(self, "_oracle_freeze", False),
                                "oracle_modifier": getattr(self, "_oracle_risk_modifier", 1.0),
                                "is_running": True,
                            },
                            "nodes": [
                                "intel_bus",
                                "brain",
                                "agent_a",
                                "agent_b",
                                "agent_c",
                                "agent_d",
                            ],
                            "timestamp": time.time_ns(),
                        }
                        await self.bus.publish("system.state", state_payload)
                    except Exception as _ws_err:
                        logger.debug(f"BrainWatchdog: state publish skipped: {_ws_err}")

                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"BrainWatchdog: Heartbeat error: {e}")
                await asyncio.sleep(5)

    # BUS LISTENER — processes events from SharedIntelligenceBus

    async def _run_bus_listener(self) -> None:
        """
        Background task: subscribes to all bus topics the Brain cares about
        and updates internal state in real-time.
        CPU fix: uses async iteration for 0% idle overhead.
        """
        if self.bus is None:
            logger.debug("BrainBusListener: no bus — skipping")
            return

        # Initialize queues
        q_oracle = self.bus.subscribe("oracle.state", maxsize=10)
        q_freeze = self.bus.subscribe("oracle.freeze", maxsize=10)
        q_calib = self.bus.subscribe("calibration.update", maxsize=50)
        q_candle = self.bus.subscribe("candle.batch", maxsize=10)
        q_tick = self.bus.subscribe("tick.hft", maxsize=100)  # Fast-Lane Pulse
        q_news = self.bus.subscribe("news.hft", maxsize=50)
        q_news_gen = self.bus.subscribe("news.event", maxsize=50)
        q_macro = self.bus.subscribe("macro.impact", maxsize=10)
        q_flow = self.bus.subscribe("institutional.flow", maxsize=50)
        q_remote = self.bus.subscribe("command.remote", maxsize=10)

        logger.info("BrainBusListener: event-driven loop active")

        async def _check_queue(q: "asyncio.Queue", label: str) -> None:
            """Process a single queue asynchronously."""
            while self.is_running:
                try:
                    payload = await q.get()  # Event-driven block (0% CPU)

                    if label == "oracle.state":
                        self._oracle_risk_modifier = float(payload.get("modifier", 1.0))
                        new_dhatu = str(payload.get("dhatu", "Sthiti"))

                        if getattr(self.loss_tracker, "consecutive_losses", 0) >= 5:
                            if new_dhatu != "Abhava":
                                logger.debug(
                                    f"Risk-Off Override: Ignoring Oracle {new_dhatu} "
                                    "due to loss streak."
                                )
                                new_dhatu = "Abhava"

                        self._oracle_dhatu = new_dhatu

                        # Only un-freeze if the new state is NOT a freeze state
                        if new_dhatu not in ("Abhava", "Viyoga"):
                            self._oracle_freeze = False

                        logger.info(
                            f" BUS → oracle.state: dhatu={self._oracle_dhatu} "
                            f"modifier={self._oracle_risk_modifier:.2f} "
                            f"(freeze={self._oracle_freeze})"
                        )

                    elif label == "oracle.freeze":
                        self._oracle_freeze = True
                        self._oracle_dhatu = str(payload.get("dhatu", "Abhava"))
                        logger.warning(
                            f"  BUS → oracle.freeze: {payload.get('dhatu')} — "
                            f"all new entries BLocked"
                        )

                    elif label == "calibration.update":
                        n = payload.get("n_trades", 0)
                        rating = payload.get("data_rating", "INSUFFICIENT")

                        if payload.get("matrix_active"):
                            top_pats = payload.get("top_patterns", [])
                            for p in top_pats:
                                key = p.get("key")
                                wr = p.get("win_rate")
                                if key and wr:
                                    self._learned_win_rates[key] = float(wr)

                        logger.info(
                            f" BUS → calibration.update: n={n} rating={rating} "
                            f"learned_keys={len(self._learned_win_rates)}"
                        )

                    elif label == "candle.batch":
                        # Pulse the state machine that new data is available
                        count = payload.get("count", 0)
                        logger.info(f" BUS → candle.batch: {count} symbols Pulse Detected.")
                        self.new_candle_event.set()

                    elif label == "tick.hft":
                        # Fast-Lane Processing: Feed the real-time reactor
                        await self.on_tick(payload)

                    elif label in ("news.hft", "news.event"):
                        # Triggers neural news bias and immediate re-scan
                        await self._on_hft_news(payload)

                    elif label == "macro.impact":
                        # Direct Macro Influence on Brain Risk
                        impact = payload.get("impact", "NEUTRAL")
                        if impact == "BEARISH":
                            self._oracle_risk_modifier *= 0.8
                        elif impact == "BULLISH":
                            self._oracle_risk_modifier = min(1.5, self._oracle_risk_modifier * 1.1)
                        logger.info(
                            f" BUS → macro.impact: {impact} | "
                            f"Adjusted Modifier: {self._oracle_risk_modifier:.2f}"
                        )

                    elif label == "institutional.flow":
                        # Order flow awareness
                        bias = payload.get("flow_bias", "NEUTRAL")
                        sym = payload.get("symbol", "")
                        logger.info(f" BUS → inst.flow [{sym}]: {bias}")

                    elif label == "command.remote":
                        cmd = payload.get("cmd")
                        if cmd == "panic":
                            logger.critical(" REMOTE COMMAND: PANIC SHIELD INITIATED")
                            await self._panic_liquidate_all()
                            self.emergency_halted = True
                        elif cmd == "status":
                            # Broadcast current stats so the Remote can see them
                            await self.bus.publish(
                                "notification.telegram",
                                {
                                    "message": (
                                        f" <b>TELEMETRY SNAPSHOT</b>\n"
                                        f"Session PnL: ${self.session_pnl:+.2f}\n"
                                        f"Open Positions: {len(self.positions)}\n"
                                        f"State: {self._oracle_dhatu}\n"
                                        f"Halted: {self.emergency_halted}"
                                    )
                                },
                            )
                        elif cmd == "dhatu_override":
                            target = payload.get("target", "ABHAVA")
                            self._oracle_dhatu = target
                            self._oracle_risk_modifier = (
                                0.0 if target == "ABHAVA" else 0.5 if target == "SHANTI" else 1.0
                            )
                            self._oracle_freeze = target == "ABHAVA"
                            logger.warning(f" REMOTE OVERRIDE: Dhatu set to {target}")

                except Exception as e:
                    logger.error(f"BrainBusListener error in {label}: {e}")
                    await asyncio.sleep(1)

        # Start concurrent processors for each queue
        await asyncio.gather(
            _check_queue(q_oracle, "oracle.state"),
            _check_queue(q_freeze, "oracle.freeze"),
            _check_queue(q_calib, "calibration.update"),
            _check_queue(q_candle, "candle.batch"),
            _check_queue(q_tick, "tick.hft"),
            _check_queue(q_news, "news.hft"),
            _check_queue(q_remote, "command.remote"),
            _check_queue(q_news_gen, "news.event"),
            _check_queue(q_macro, "macro.impact"),
            _check_queue(q_flow, "institutional.flow"),
        )

    # HIGH-SPEED REACTOR — processes 10ms ticker data

    async def get_current_spread(self, symbol: str) -> dict[str, float]:
        """Returns the last known bid, ask, and spread for a symbol."""
        bid = self.last_tick_bids.get(symbol, self.last_tick_prices.get(symbol, 0.0))
        ask = self.last_tick_asks.get(symbol, self.last_tick_prices.get(symbol, 0.0))

        # If we have no data, return a default nominal spread (0.01% of price)
        if bid == 0 or ask == 0:
            return {"bid": 0.0, "ask": 0.0, "spread": 0.0, "mid": 0.0}

        return {"bid": bid, "ask": ask, "spread": abs(ask - bid), "mid": (ask + bid) / 2.0}

    async def on_tick(self, data: dict[str, Any]) -> None:
        """
        Sovereign Fast-Path: Processes 10ms ticks to detect immediate entry levels.
        Bypasses the 60s candle loop for high-fidelity 'Strikes'.
        """
        symbol = data.get("symbol")
        price = data.get("price")
        if not symbol or price is None:
            return

        # 1. Update Real-time Matrix Memory
        self.last_tick_prices[symbol] = float(price)
        self.last_tick_bids[symbol] = float(data.get("bid", price))
        self.last_tick_asks[symbol] = float(data.get("ask", price))

        if symbol == "SPY":
            self.spy_buffer.append(float(price))

        self.new_tick_event.set()

        # 2. Strike-Zone Evaluation (Additive logic)
        # If we are in SCANNING state and have a high-confidence zone waiting,
        # we trigger the entry IMMEDIATELY on price hit.
        if self.state == TradingState.SCANNING:
            # This bypasses the 5s/60s sleep in _state_scanning
            # Logic handled by the 'Sovereign Strike' accelerator block
            pass

    async def _state_standby(self) -> None:
        """Wait for market open + generate morning budget."""
        # Ensure DMS doesn't emergency flatten us while we wait for market open
        if self.dms:
            self.dms.record_heartbeat("BRAIN_PRIMARY")

        now = datetime.now(timezone.utc)

        # 1. Update drawdown ladders
        await self._update_drawdowns()

        # 2. Check regime (MUST happen before budget generation)
        logger.info("STANDBY: Detecting market regime...")
        try:
            # Timeout-guarded regime detection to prevent startup stalls
            self.current_regime = await asyncio.wait_for(self._detect_regime(), timeout=20.0)
            logger.info(f"STANDBY: Market Regime detected as {self.current_regime}")
        except Exception as e:
            logger.warning(
                f"STANDBY: Regime detection timed out/failed ({e}) - using CHOPPY default"
            )
            self.current_regime = "CHOPPY"

        # 3. Generate morning budget once per day at 8 AM ET window
        last_budget = self.last_budget_date
        if last_budget is None or last_budget.date() != now.date():
            await self._generate_morning_budget()

        # Check if any drawdown prevents trading
        if not self.ibkr_drawdown.is_trading_allowed():
            logger.warning(f"IBKR drawdown [{self.ibkr_drawdown.level.value}] — trading suspended")
            await asyncio.sleep(60)
            return

        if not self.loss_tracker.is_trading_allowed():
            logger.warning(
                "G1 escalation — trading suspended "
                f"(consecutive losses: {self.loss_tracker.consecutive_losses})"
            )
            await asyncio.sleep(60)
            return

        # Advance to scanning
        async with self._state_lock:
            self.state = TradingState.SCANNING
        logger.info("[SOVEREIGN] MATRIX STATE: STANDBY -> SCANNING")

    async def _generate_morning_budget(self) -> None:
        """Generate morning risk budget using Agent A logic."""
        self.morning_budget.generate(
            regime=self.current_regime,
            consecutive_losses=self.loss_tracker.consecutive_losses,
            dd_level=self.ibkr_drawdown.level,
        )
        self.last_budget_date = datetime.now(timezone.utc)

    # STATE: SCANNING

    async def _state_scanning(self) -> None:
        """Agent A scans for pattern opportunities in parallel."""

        # Wait up to 5 s for a candle.batch pulse from the data pipeline.
        # If none arrives (pipeline offline / first-run warmup), SCAN ANYWAY
        # on the fallback clock so the engine is never permanently starved.
        # Previously this block had a bare `return` on TimeoutError which
        # caused the scanner to NEVER execute any pattern detection when the
        # pipeline was slow or offline — the primary cause of zero trades.
        if self.bus is not None:
            candle_task = asyncio.create_task(self.new_candle_event.wait())
            tick_task = asyncio.create_task(self.new_tick_event.wait())
            try:
                done, pending = await asyncio.wait(
                    [candle_task, tick_task], timeout=5.0, return_when=asyncio.FIRST_COMPLETED
                )
            except (asyncio.TimeoutError, TimeoutError, Exception):
                _done, _pending = set(), {candle_task, tick_task}
            finally:
                for task in [candle_task, tick_task]:
                    if not task.done():
                        task.cancel()

                self.new_candle_event.clear()
                self.new_tick_event.clear()

        # Execute the actual pattern discovery logic
        await self._run_scanning_cycle()

    async def _run_scanning_cycle(self) -> None:
        """
        Sovereign Matrix Scan.
        Concurrent Scan Protection
        """
        if getattr(self, "_is_scanning", False):
            return
        self._is_scanning = True

        try:
            now = datetime.now(timezone.utc)
            if (
                self.last_regime_update is None
                or (now - self.last_regime_update).total_seconds() >= 60
            ):
                try:
                    # Use a short timeout so regime detection doesn't stall the scanning pulse
                    new_regime = await asyncio.wait_for(self._detect_regime(), timeout=10.0)
                    if new_regime != self.current_regime:
                        logger.info(
                            f"[SOVEREIGN] REGIME SHIFT: {self.current_regime} -> {new_regime}"
                        )
                        self.current_regime = new_regime
                    self.last_regime_update = now
                except Exception as e:
                    logger.debug(f"Regime refresh failed ({e}) — keeping {self.current_regime}")

            self._scan_cycle += 1

            # Check budget with atomic safety
            if not self.budget_monitor.is_trading_allowed():
                logger.warning("SCAN BLOCKED: Budget exhausted — returning to STANDBY")
                async with self._state_lock:
                    self.state = TradingState.STANDBY
                await asyncio.sleep(60)
                return

            watchlist = await self._get_watchlist()

            broker_online = False
            if self.mode == "paper":
                broker_online = True
            elif self.mode == "ibkr_paper":
                broker_online = (
                    hasattr(self.ibkr_conn, "is_connected") and self.ibkr_conn.is_connected
                )
            elif self.active_broker == "IBKR":
                broker_online = (
                    hasattr(self.ibkr_conn, "is_connected") and self.ibkr_conn.is_connected
                )
            elif self.active_broker == "MT5":
                broker_online = (
                    hasattr(self.mt5_conn, "is_connected") and self.mt5_conn.is_connected
                )

            if not broker_online:
                if self._scan_cycle % 10 == 1:
                    logger.info(f"SCAN SUSPENDED: [{self.active_broker}] is currently offline.")
                await asyncio.sleep(5)
                return

            # Diagnostics
            stats = {
                "scanned": 0,
                "no_data": 0,
                "stale": 0,
                "too_short": 0,
                "detected": 0,
                "approved": 0,
                "rejected": 0,
            }
            stats_lock = asyncio.Lock()

            # 1. DMS HEARTBEAT
            if self.dms:
                self.dms.record_heartbeat("BRAIN_PRIMARY")

            async def _scan_symbol(symbol: str):
                from mind_ultrathink import LatencyWatchdog

                async with stats_lock:
                    stats["scanned"] += 1

                if self._scan_cycle % 10 == 0:
                    logger.info(f"[SCAN] Sovereign Probe: Scanning {symbol}...")

                if self.bus:
                    await self.bus.publish(
                        "system.pulse",
                        {
                            "type": "telemetry.pulse",
                            "agent": "agent_a",
                            "symbol": symbol,
                            "timestamp": time.time() * 1000,
                        },
                    )

                with LatencyWatchdog(f"Scan:{symbol}", threshold_ms=10000.0):
                    try:
                        fetch_result = await self._fetch_ohlcv(symbol)
                        if fetch_result is None or isinstance(fetch_result, str):
                            async with stats_lock:
                                stats["no_data"] += 1
                            return None

                        df_pd = fetch_result
                        if len(df_pd) < 50:
                            async with stats_lock:
                                stats["too_short"] += 1
                            return None

                        # Essential for MindMath deterministic auditing.
                        # Convert to Polars once for high-performance vectorized math
                        if isinstance(df_pd, pl.DataFrame):
                            df_pl = df_pd
                        else:
                            df_pl = pl.from_pandas(df_pd)

                        tr_expr = pl.max_horizontal(
                            [
                                (pl.col("high") - pl.col("low")).abs(),
                                (pl.col("high") - pl.col("close").shift(1)).abs(),
                                (pl.col("low") - pl.col("close").shift(1)).abs(),
                            ]
                        ).alias("tr")

                        tr = df_pl.select([tr_expr])["tr"]
                        atr_val = float(tr.tail(20).mean()) if len(tr) >= 20 else 0.0

                        # Offload CPU-heavy pattern detection to a thread pool
                        # to avoid blocking the event loop
                        # Pass the Polars DataFrame as expected by agent_a
                        patterns = await asyncio.to_thread(self.pattern_detector.detect_all, df_pl)
                        for p in patterns:
                            if p:
                                p.atr = atr_val

                        found = [p for p in patterns if p and p.confidence >= 60.0]

                        if not found:
                            all_found = [p for p in patterns if p]
                            if all_found:
                                async with stats_lock:
                                    stats["detected"] += 1
                                    stats["rejected"] += 1
                                best_low = max(all_found, key=lambda x: x.confidence)
                                logger.info(
                                    f"Scan [{symbol}]: Pattern {best_low.name} detected but "
                                    f"confidence {best_low.confidence}% too low."
                                )
                            return None

                        best = max(found, key=lambda x: x.confidence)
                        async with stats_lock:
                            stats["detected"] += 1
                            stats["approved"] += 1

                        logger.info(
                            f" DISCOVERY: {symbol} matched {best.name} ({best.confidence:.1f}%)"
                        )

                        # Logging every scan discovery caused 1.3M row bloat in 12 hours.
                        # Only real trade attempts and vetos are now logged by the Coordinator.
                        # try:
                        #     LEDGER.record_entry(
                        #         symbol=symbol,
                        #         pattern=best.name,
                        #         confidence=best.confidence,
                        #         agent_votes={
                        #             "agent_a": (
                        #                 f"{best.name} ({best.confidence:.1f}%) — "
                        #                 f"R/R {getattr(best, 'r_r_ratio', 0):.1f}x"
                        #             )
                        #         },
                        #         triggered_by="agent_a",
                        #         meta={
                        #             "regime": self.current_regime,
                        #             "dhatu": self._oracle_dhatu,
                        #             "oracle_modifier": self._oracle_risk_modifier,
                        #         },
                        #     )
                        # except Exception as _le:
                        #     logger.debug(f"DecisionLedger entry skipped: {_le}")

                        task = self.task_manager.spawn_trade(
                            symbol, {"pattern": best.name, "conf": best.confidence}
                        )
                        task.log(f"DISCOVERY_HIT: {best.name} detected.")

                        return {
                            "symbol": symbol,
                            "pattern": best,
                            "lambda": best.confidence / 100.0,
                            "task": task,
                        }

                    except Exception as e:
                        logger.warning(f"Error scanning {symbol}: {e}", exc_info=True)
                        return None

            results = []
            for i in range(0, len(watchlist), 3):
                batch = watchlist[i : i + 3]
                batch_results = await asyncio.gather(*[_scan_symbol(s.upper()) for s in batch])
                results.extend(batch_results)

                if self.mind_ghost:
                    await self.mind_ghost.update_heartbeat("ENGINE")

                await asyncio.sleep(0.1)

            discoveries = [r for r in results if r is not None]

            vix = await self._get_vix()
            vix_str = f"{vix:.2f}" if vix > 0 else "N/A"
            logger.info(
                f"[SCAN] #{self._scan_cycle} | Regime={self.current_regime} | "
                f"Condition={self._oracle_dhatu} (VIX: {vix_str}) "
                f"| Watchlist={len(watchlist)} Scanned={stats['scanned']} "
                f"| Detected={stats['detected']} Approved={stats['approved']} "
                f"| Pending={len(discoveries)}"
            )

            # Update global stats with lock
            async with self._state_lock:
                self.last_scan_stats = {
                    "cycle": self._scan_cycle,
                    "watchlist": len(watchlist),
                    "scanned": stats["scanned"],
                    "patterns_detected": stats["detected"],
                    "patterns_approved": stats["approved"],
                    "pending": len(discoveries),
                    "regime": self.current_regime,
                }

            # Routine Memory Maintenance (Every 10 cycles)
            if self.task_manager and self._scan_cycle % 10 == 0:
                self.task_manager.purge_dormant_tasks(max_age_minutes=15)

            # Prevent 'Information Overload' by clearing buffers when signal density is too high.
            # Guard: skip entropy check if no symbols were successfully scanned
            # to avoid false flushes.
            scanned_count = stats["scanned"]
            # Corrected: Density should reflect actual Task Registry occupancy
            # (Volume), not Hit Rate.
            # Hit rate is a measure of opportunity; Registry occupancy is a measure of memory load.
            # We only flush if we are approaching the 1000-task hard limit.
            signal_density = len(self.task_manager.tasks) / 1000.0 if self.task_manager else 0.0

            # Use a time-based cooldown (max 1 flush per 60 seconds) to prevent log spam
            now = time.monotonic()
            if signal_density > 0.8:
                if (
                    not hasattr(self, "_last_entropy_flush")
                    or now - getattr(self, "_last_entropy_flush", 0) > 60
                ):
                    logger.warning(
                        "SYSTEM ENTROPY CRITICAL "
                        f"(Density: {signal_density:.2f}): Performing Cognitive Flush..."
                    )
                    self._last_entropy_flush = now

                # FINALIZATION FIX: Ensure tasks are not leaked during flush
                for d in self.pending_signals + discoveries:
                    task = d.get("task")
                    if task and hasattr(task, "finalize"):
                        task.finalize("VETOED")

                self.pending_signals.clear()
                discoveries.clear()  # Ensure we don't immediately refill pending_signals
                # Also clear old closed positions to free memory
                if len(self.closed_positions) > 100:
                    for _ in range(50):
                        self.closed_positions.popleft()

                # SOVEREIGN REGISTRY FLUSH: At critical density (≥95%), actively purge
                # stale PENDING tasks from the TaskManager to free capacity.
                # Without this, the registry fills to 1000 and the brain stalls.
                if signal_density >= 0.95 and self.task_manager:
                    from sovereign_task import TaskStatus
                    purged = 0
                    stale_keys = [
                        k for k, t in list(self.task_manager.tasks.items())
                        if hasattr(t, "status") and t.status == TaskStatus.PENDING
                    ]
                    for k in stale_keys[:200]:  # Purge up to 200 oldest PENDING tasks
                        task = self.task_manager.tasks.pop(k, None)
                        if task and hasattr(task, "finalize"):
                            task.finalize("ENTROPY_FLUSH")
                        purged += 1
                    if purged:
                        logger.warning(
                            f"SOVEREIGN REGISTRY FLUSH: Purged {purged} stale PENDING tasks "
                            f"(Registry was at {signal_density:.0%} capacity)."
                        )

            if discoveries:
                self.pending_signals = discoveries
                async with self._state_lock:
                    self.state = TradingState.ANALYZING
            else:
                vix = await self._get_vix()
                nap_time = self.scan_interval if vix < 25 else (self.scan_interval / 2.0)
                await asyncio.sleep(nap_time)

        finally:
            self._is_scanning = False

    # STATE: ANALYZING

    async def _state_analyzing(self) -> None:
        """
        Phase-Based Veting Lifecycle (Agent M Coordinator).
        Concurrent Task-Graph Orchestration (Pillar 3).
        Spawns parallel vetting tasks for all pending signals.
        """
        if not self.pending_signals:
            self.state = TradingState.SCANNING
            return

        logger.info(
            f"TradingBrain: Spawning {len(self.pending_signals)} "
            "Parallel Vetting Tasks (Agent M)..."
        )

        def _task_done(t):
            try:
                t.result()
            except asyncio.CancelledError:
                pass  # Graceful exit on shutdown
            except Exception as e:
                logger.error(f"MATRIX CRITICAL: Coordinator task crashed: {e}")

        for signal in self.pending_signals:
            symbol = signal.get("symbol")
            task_obj = signal.get("task")
            task_id = task_obj.id if task_obj else "N/A"
            logger.info(
                f"MindBrain: Handing off Task {task_id} ({symbol}) to Coordinator Fortress."
            )

            vetting_task = asyncio.create_task(
                self.coordinator.initiate_trade_lifecycle(symbol, signal)
            )
            vetting_task.add_done_callback(_task_done)

        # Clear the queue and return to scanning immediately
        self.pending_signals = []
        async with self._state_lock:
            self.state = TradingState.SCANNING

    # STATE: POSITIONED

    async def _state_positioned(self) -> None:
        """Monitor active positions using 7-Level Exit Intelligence Engine."""
        # Ensures orphan trades like GOOGL/SMCI are caught even if missed at startup
        self._sanitize_positions()  # Ensure memory is objects, not dicts
        await self._reconcile_broker_positions()

        logger.debug(f"MONITORING {len(self.positions)} active positions")

        exits_triggered = []

        for pos in list(self.positions):  # type: ignore
            if pos.meta.get("exit_triggered"):
                continue

            if abs(pos.qty) < 0.0001:
                # Ghost position (flattened externally). Skip monitoring to avoid 0-unit finalizations.
                continue

            try:
                # Fetch live market data for this position
                market_data = await self._fetch_market_snapshot(pos.symbol)
                current_price = (
                    market_data.get("price")
                    if market_data and market_data.get("price") is not None
                    else pos.entry_price
                )
                vix = market_data.get("vix", 18.0) if market_data else 18.0

                # Update Bayesian belief and real-time PnL
                pos.current_price = current_price
                pos.unrealized_pnl = (current_price - pos.entry_price) * pos.qty

                # Check IBKR cache to stop 'Phantom Tightening' logs
                broker_qty = 0
                if hasattr(self, "agent_c_ibkr") and self.agent_c_ibkr.ibkr_conn:
                    broker_qty = self.agent_c_ibkr.ibkr_conn._positions_cache.get(pos.symbol, 0)

                pos.meta["broker_flat"] = abs(broker_qty) < 0.1

                # MFE / MAE Tracking
                risk_amt = abs(pos.entry_price - pos.initial_stop)
                if risk_amt < 0.0001:
                    risk_amt = 0.01  # Prevent ZeroDivision

                gross_r = (
                    ((current_price - pos.entry_price) / risk_amt)
                    if pos.qty > 0
                    else ((pos.entry_price - current_price) / risk_amt)
                )
                pos.mfe = max(pos.mfe, gross_r)
                pos.mae = min(pos.mae, gross_r)

                if current_price > pos.entry_price:
                    pos.current_belief = min(pos.current_belief * 1.01, 0.99)
                elif current_price < pos.entry_price:
                    pos.current_belief = max(pos.current_belief * 0.98, 0.01)

                # Check take profit
                if current_price >= pos.take_profit and pos.account_type != "short":
                    # Do not exit instantly on Target, wait for ExitIntelligence
                    # to scale-out/runner.
                    pass

                # Build dictionaries for Exit Intelligence Engine
                pos_dict = {
                    "symbol": pos.symbol,
                    "side": "long" if pos.qty > 0 else "short",
                    "quantity": abs(pos.qty),
                    "entry_price": pos.entry_price,
                    "stop_loss": pos.stop_loss,
                    "initial_stop": pos.initial_stop,
                    "bayesian_belief": pos.current_belief,
                    "initial_belief": pos.initial_belief,
                    "mfe_r": pos.mfe,
                    "runner_active": getattr(pos, "runner_active", False),
                }
                market_dict = {
                    "price": current_price,
                    "vix": vix,
                    "vix_baseline": 15.0,
                }
                account_dict = {
                    "equity": await self._get_account_value(pos.account_type),
                    "daily_pnl": await self._get_daily_pnl(pos.account_type),
                }

                # Perform a 500ms 'Heartbeat Re-vet' using Mind_Ultrathink
                # This checks if the reasons we entered the trade are still valid.
                thought_dna = await self.mind_ultrathink.heartbeat_vet(pos_dict, market_dict)
                if thought_dna.get("veto"):
                    logger.warning(
                        f" Sovereign HEARTBEAT VETO: {pos.symbol} — {thought_dna.get('reason')}"
                    )
                    exits_triggered.append((pos, "HEARTBEAT_VETO", current_price))
                    continue  # Skip further monitoring for this tick

                # Dynamic Stop Adjustment from Thought DNA (Beta Gate)
                if thought_dna.get("new_stop"):
                    pos.stop_loss = float(thought_dna["new_stop"])

                # 7-level priority evaluation (Standard Engine)
                decision = self.exit_engine.evaluate(
                    pos_dict, market_dict, account_dict, self._oracle_dhatu
                )

                if decision.action == ExitAction.EXIT:
                    logger.info(f"EXIT P{decision.priority}: {pos.symbol} — {decision.reason}")
                    # Gate is now set inside _process_exit to prevent race conditions
                    exits_triggered.append((pos, f"EXIT_P{decision.priority}", current_price))

                elif decision.action == ExitAction.PARTIAL:
                    if not getattr(pos, "runner_active", False):
                        logger.info(f"PARTIAL (Runner Setup): {pos.symbol} at {current_price}")
                        pos.runner_active = True
                        pos.shares_remaining = 0.5  # keep 50%
                        exits_triggered.append((pos, "PARTIAL", current_price))

                elif decision.action == ExitAction.TIGHTEN:
                    if decision.new_stop is not None:
                        old_stop = pos.stop_loss
                        pos.stop_loss = decision.new_stop

                        # Only log if the position actually still exists in reality
                        if not pos.meta.get("broker_flat", False):
                            logger.info(
                                f"TIGHTEN: {pos.symbol} stop ${old_stop:.2f} -> "
                                f"${pos.stop_loss:.2f}"
                            )
                        else:
                            logger.debug(
                                f"Sovereign [Quiet-Sync]: Tightened phantom stop for "
                                f"{pos.symbol} (Flat)."
                            )

                elif decision.action == ExitAction.CASCADE:
                    logger.warning(f"CASCADE: {pos.symbol} — correlated exits detected")
                    exits_triggered.append((pos, "CASCADE", current_price))

                elif decision.action == ExitAction.EVALUATE:
                    logger.info(f"EVALUATE: {pos.symbol} — {decision.reason}")

                elif decision.action == ExitAction.HOLD:
                    if self.bus:
                        await self.bus.publish(
                            "exit.skipped",
                            {
                                "symbol": pos.symbol,
                                "reason": decision.reason,
                                "timestamp": time.time_ns(),
                            },
                        )

                # VIX intraday protocol check
                vix_action = self.vix_protocol.monitor_intraday(vix, vix, vix)
                # Publish calibration.update so Brain can tune thresholds live
                if vix_action == "CLOSE at market":
                    logger.warning(f"VIX PROTOCOL: Close {pos.symbol} immediately")
                    exits_triggered.append((pos, "VIX_PROTOCOL", current_price))

            except Exception as e:
                logger.error(f"Error monitoring {pos.symbol}: {e}")

        # Process exits
        for pos, exit_type, exit_price in exits_triggered:
            # Flag as triggered immediately to block the next tick from spamming
            pos.meta["exit_triggered"] = True
            await self._process_exit(pos, exit_type, exit_price)

        if not self.positions:
            async with self._state_lock:
                self.state = TradingState.SCANNING

    # Legacy _process_exit (RE-REMOVED for System Integrity).
    # This block was re-poisoning the session file with dict-based serialization.

    # STATE: EXIT

    async def _state_exit(self) -> None:
        """Cleanup after exits and feed Agent D."""
        logger.debug("PROCESSING exits and feeding Agent D calibration pipeline")

        # Agent D learning happens in _process_exit
        async with self._state_lock:
            self.state = TradingState.SCANNING
        await asyncio.sleep(1)

    # COGNITIVE TOOLS (Execution-Brain tools for the Minds)

    async def _tool_get_account_status(self, account_type: str = "ibkr") -> dict[str, Any]:
        """Provides the Master Mind (Evolution) with the real-time equity curve."""
        logger.debug(f"MindBridge: Fetching account health for {account_type}...")
        equity = await self._get_account_value(account_type)
        daily_pnl = await self._get_daily_pnl(account_type)

        unrealized_pnl = 0.0
        if account_type == "ibkr" and self.ibkr_client and self.ibkr_client.isConnected():
            acc_vals = self.ibkr_client.accountValues()
            unrealized_pnl = next(
                (float(x.value) for x in acc_vals if x.tag == "UnrealizedPnL"), 0.0
            )

        return {
            "equity": equity,
            "daily_pnl": daily_pnl,
            "unrealized_pnl": unrealized_pnl,
            "peak_equity": self.ibkr_drawdown.peak_equity
            if account_type == "ibkr"
            else self.prop_drawdown.peak_equity,
            "status": "OK" if not self.emergency_halted else "HALTED",
        }

    async def _tool_get_open_positions(self) -> dict[str, Any]:
        """Provides the Healer Mind (Architect) with the live positional context."""
        async with self._state_lock:
            pos_data = []
            for p in self.positions:
                pos_data.append(
                    {
                        "symbol": p.symbol,
                        "qty": p.qty,
                        "unrealized_pnl": p.unrealized_pnl,
                        "belief": p.current_belief,
                    }
                )
        return {"positions": pos_data, "count": len(pos_data)}

    # INTERNAL HELPERS

    async def _handle_emergency(self) -> None:
        """Emergency flatten procedure — flatten all positions."""
        logger.critical("EMERGENCY HALT — Attempting to flatten ALL positions")

        from telegram_alerts import send_telegram_alert

        await send_telegram_alert(
            " *EMERGENCY HALT* \nAttempting to flatten ALL positions due to critical system error."
        )

        for pos in list(self.positions):  # type: ignore
            try:
                if pos.account_type == "ibkr" and self.ibkr_client:
                    logger.warning(f"Emergency flatten {pos.symbol} on IBKR")
                    await self._place_ibkr_order(pos.symbol, "SELL", int(pos.qty))
                elif pos.account_type == "mt5" and self.mt5_conn:
                    logger.warning(f"Emergency flatten {pos.symbol} on MT5")
                    ticket_str = str(pos.trade_id).replace("RESTORED-", "")
                    try:
                        ticket = int(ticket_str)
                        await asyncio.to_thread(self.mt5_conn.close_position, ticket)
                    except ValueError:
                        logger.error(
                            f"MT5: Emergency flatten failed for {pos.symbol} (Invalid Ticket)"
                        )
            except Exception as e:
                logger.error(f"Failed to flatten {pos.symbol}: {e}")

        async with self._state_lock:
            self.positions.clear()
            self.state = TradingState.STANDBY
        await asyncio.sleep(30)

    # EXIT PROCESSING

    async def _process_exit(self, pos: Position, exit_type: str, exit_price: float) -> None:
        """Standardized Exit Resolver (Pillar 5 Upgrade)."""
        try:
            symbol = pos.symbol
            now = datetime.now(timezone.utc)

            # SOVEREIGN BYPASS: Always allow emergency exits (STOP, VETO, VIX, SAFETY)
            # regardless of age or cooldown to prevent account damage during volatility.
            is_emergency = any(
                term in exit_type.upper() for term in ["STOP", "VIX", "VETO", "SAFETY"]
            )

            # Skip exit processing if broker is currently offline.
            # This prevents 3-strike lockouts caused by temporary connection blips.
            broker_online = False
            if self.mode == "paper":
                broker_online = True
            elif pos.account_type == "ibkr":
                broker_online = (
                    hasattr(self.ibkr_conn, "is_connected") and self.ibkr_conn.is_connected
                )
            elif pos.account_type == "mt5":
                broker_online = (
                    hasattr(self.mt5_conn, "is_connected") and self.mt5_conn.is_connected
                )

            if not broker_online:
                logger.warning(
                    f"DELAYED EXIT [{symbol}]: {pos.account_type} is OFFLINE. Postponing pulse."
                )
                return

            # Strike-3 Lockout check
            strikes = self._exit_failure_count.get(symbol, 0)
            if strikes >= 3:
                logger.critical(
                    f"STRIKE-3 LOCKOUT: {symbol} has 3 failed exit attempts. "
                    "Automated execution HALTED to prevent account damage. "
                    "HUMAN INTERVENTION REQUIRED."
                )
                return

            # Cooldown Dampener (10s)
            last_attempt = self._exit_last_attempt.get(
                symbol, datetime(1970, 1, 1, tzinfo=timezone.utc)
            )
            if (now - last_attempt).total_seconds() < 10 and not is_emergency:
                logger.warning(
                    f"DAMPENER ACTIVE: {symbol} exit attempt suppressed. "
                    f"Waiting for cooldown (Last try: {last_attempt.strftime('%H:%M:%S')})."
                )
                return

            # Prevent "Wash Trades" by enforcing a 15-minute minimum hold time
            # unless it is an emergency or hard-stop hit.
            # Guard: ensure entry_time is timezone-aware before subtraction
            entry_time = pos.entry_time
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)
            age_seconds = (now - entry_time).total_seconds()

            # (Emergency bypass logic handled at top)

            if age_seconds < 100 and not is_emergency:
                logger.warning(
                    f" EXIT IMMUNITY: Rejecting {exit_type} exit for {symbol}. "
                    f"Position is only {age_seconds:.0f}s old. Minimum hold: 100s."
                )
                return

            # Keep track of this attempt
            self._exit_last_attempt[symbol] = now

            # 1. Physical Exit (Broker Handshake)
            direction = "SELL" if pos.qty > 0 else "BUY"

            # Handling Partials
            if exit_type == "PARTIAL":
                exit_shares = max(1, abs(int(pos.qty * 0.5)))
            else:
                exit_shares = abs(int(pos.qty))

            if exit_shares == 0:
                logger.warning(f" SKIPPING EXIT for {symbol}: Position size is already 0.")
                if pos in self.positions:
                    self.positions.remove(pos)
                self._mark_trade_liquidated(symbol, pos.account_type)
                return

            # Check if we already have an active order for this symbol at the broker.
            # allow the Brain to re-submit as a fresh Market Order on this tick.
            if self.ibkr_client and pos.account_type == "ibkr":
                active_trades = [
                    t
                    for t in self.ibkr_client.trades()
                    if t.contract.symbol == pos.symbol and not t.isDone()
                ]
                if active_trades:
                    # Check staleness — if order is >45 seconds old, cancel and re-submit
                    STALE_THRESHOLD_SEC = 45
                    stale_found = False
                    for stale_trade in active_trades:
                        order_id = stale_trade.order.orderId
                        submitted_at = self._order_submit_times.get(order_id, now)
                        age_sec = (now - submitted_at).total_seconds()
                        if age_sec > STALE_THRESHOLD_SEC:
                            logger.warning(
                                f" STALE ORDER ESCALATION: {pos.symbol} order #{order_id} "
                                f"is {age_sec:.0f}s old without fill. "
                                "Cancelling and re-submitting as MKT."
                            )
                            try:
                                self.ibkr_client.cancelOrder(stale_trade.order)
                                self._order_submit_times.pop(order_id, None)
                            except Exception as cancel_err:
                                logger.warning(
                                    f"Cancel failed for {pos.symbol} #{order_id}: {cancel_err}"
                                )
                            stale_found = True
                    if not stale_found:
                        logger.warning(
                            f" ORDER SHIELD: Suppressing {exit_type} for {pos.symbol}. "
                            "Active order already exists."
                        )
                        return
                    # else: stale order cancelled — fall through to re-submit below

            logger.warning(
                f"EXECUTING {exit_type} FOR {pos.symbol} | "
                f"PRICE: ${exit_price:.2f} (Attempt: {strikes + 1})"
            )

            order_result = "SUCCESS"  # Default for paper mode or simulations
            if exit_shares > 0 and self.mode != "paper":
                if pos.account_type == "ibkr":
                    # Use 'EMERGENCY' urgency for VETOs to force true Market Orders
                    urg_level = (
                        "EMERGENCY" if "VETO" in exit_type or "FLATTEN" in exit_type else "HIGH"
                    )
                    order_result = await self._place_ibkr_order(
                        pos.symbol,
                        direction,
                        exit_shares,
                        urgency=urg_level,
                        limit_price=exit_price,
                    )
                    if order_result in [None, "SHIELDED"]:
                        logger.info(
                            f" EXIT SUSPENDED [{symbol}]: Broker order was {order_result}. "
                            "Retaining position in memory."
                        )
                        return

                elif pos.account_type == "mt5" and self.mt5_conn:
                    logger.warning(f"EXECUTING MT5 EXIT FOR {pos.symbol} (Ticket: {pos.trade_id})")
                    ticket_str = str(pos.trade_id).replace("RESTORED-", "")
                    try:
                        ticket = int(ticket_str)
                        success = await asyncio.to_thread(self.mt5_conn.close_position, ticket)
                        if not success:
                            logger.error(f"MT5: Failed to close ticket {ticket}. Retaining position.")
                            return
                    except ValueError:
                        logger.error(
                            f"MT5: Failed to parse ticket ID from '{pos.trade_id}' for {pos.symbol}"
                        )
                        return

            # 2. Mathematical Reflection
            slice_qty = exit_shares if pos.qty > 0 else -exit_shares
            # Removed redundant expression
            r_multiple = (
                ((exit_price - pos.entry_price) / abs(pos.entry_price - pos.stop_loss))
                * (1 if pos.qty > 0 else -1)
                if abs(pos.entry_price - pos.stop_loss) > 0
                else 0
            )

            intended_price = getattr(pos, "target", exit_price)
            slippage_pct = abs(exit_price - intended_price) / max(intended_price, 0.01)
            is_dirty = slippage_pct > 0.005  # 50bps threshold
            if is_dirty:
                logger.warning(
                    f"SLIPPAGE DETECTED: {pos.symbol} fill deviated {slippage_pct:.2%} "
                    "from target. Trade marked as DIRTY."
                )

            commission_cost = max(2.0, exit_shares * 0.005)
            vol_multiplier = 1.0 + (exit_shares / 2000.0)
            slippage_penalty = exit_price * 0.0005 * vol_multiplier
            adjusted_exit_price = (
                exit_price - slippage_penalty if slice_qty > 0 else exit_price + slippage_penalty
            )

            from decimal import Decimal

            d_exit = Decimal(str(adjusted_exit_price))
            d_entry = Decimal(str(pos.entry_price))
            d_qty = Decimal(str(slice_qty))
            d_comm = Decimal(str(commission_cost))
            d_slip = Decimal(str(pos.slippage_cost))
            d_total_qty = Decimal(str(abs(pos.qty) or 1))

            realized_net_pnl = float(
                (d_exit - d_entry) * d_qty
                - d_comm
                - (d_slip * (Decimal(str(exit_shares)) / d_total_qty))
            )

            # 3. Virtual Reflection (Wisdom & Skills)
            self.session_pnl += realized_net_pnl
            if exit_type != "PARTIAL":
                await self._log_trade_exit(
                    pos, exit_type, adjusted_exit_price, realized_net_pnl, r_multiple
                )

            # 4. Neural Cleanup & Learning
            if exit_type == "PARTIAL":
                old_qty = abs(pos.qty)
                if pos.qty > 0:
                    pos.qty -= exit_shares
                else:
                    pos.qty += exit_shares
                pos.shares_remaining = abs(pos.qty) / old_qty if old_qty > 0 else 0.0
            else:
                if self.mode == "paper":
                    async with self._state_lock:
                        if pos in self.positions:
                            self.positions.remove(pos)
                    self.closed_positions.append(pos)

                PORTFOLIO_ANALYZER.record_close(
                    symbol=pos.symbol,
                    side="LONG" if pos.qty > 0 else "SHORT",
                    quantity=abs(pos.qty),
                    entry_price=pos.entry_price,
                    exit_price=adjusted_exit_price,
                    pnl_usd=realized_net_pnl,
                    ts_entry=pos.entry_time,
                    ts_exit=now,
                )

                try:
                    LEDGER.record_exit(
                        symbol=pos.symbol,
                        exit_type=exit_type,
                        pnl_usd=realized_net_pnl,
                        r_multiple=r_multiple,
                        triggered_by="exit_intelligence",
                        agent_votes={"exit_intelligence": exit_type},
                        override="DIRTY_FILL" if is_dirty else "",
                        meta={
                            "entry_price": pos.entry_price,
                            "exit_price": adjusted_exit_price,
                            "slippage_pct": round(slippage_pct, 5),
                            "regime": self.current_regime,
                            "pattern": pos.pattern or "",
                        },
                    )
                except Exception as _le:
                    logger.debug(f"DecisionLedger exit skipped: {_le}")

                # Reset failure count on successful full exit
                self._exit_failure_count[symbol] = 0

                if not hasattr(self, "_loss_streak"):
                    self._loss_streak = 0

                # Guard: Do NOT count ghost (0-unit) or broker-veto exits as loss streaks.
                # These are infrastructure events, not real trading failures. Counting them
                # would prematurely trigger ABHAVA lockdown based on phantom data.
                _is_ghost_loss = abs(exit_shares) < 0.0001
                _is_veto_exit = exit_type in ("HEARTBEAT_VETO", "LIQUIDATED")
                _is_countable_loss = not _is_ghost_loss and not _is_veto_exit

                if realized_net_pnl < 0 and _is_countable_loss:
                    self._loss_streak += 1
                    if self._loss_streak >= 5:
                        logger.critical(
                            f" LOSS STREAK DETECTED ({self._loss_streak}). "
                            "TRIGGERING RISK-OFF REGIME."
                        )
                        self.current_regime = "RISK_OFF"
                        # Reset streak after triggering so we can eventually recover
                        self._loss_streak = 0
                elif realized_net_pnl >= 0 or not _is_countable_loss:
                    self._loss_streak = 0

            if hasattr(self, "recursive_evolution"):
                self.recursive_evolution.evolve_live(
                    pattern_name=pos.pattern or pos.meta.get("pattern", "UNKNOWN"),
                    pnl=realized_net_pnl,
                    regime=self.current_regime,
                    shares_remaining=getattr(pos, "shares_remaining", 0.0),
                )

            if self.bus:
                await self.bus.publish(
                    "trade.exit",
                    {
                        "symbol": pos.symbol,
                        "pnl": realized_net_pnl,
                        "exit_type": exit_type,
                        "is_dirty": is_dirty,
                        "pattern": pos.pattern or pos.meta.get("pattern", "UNKNOWN"),
                        "regime": self.current_regime,
                        "r_multiple": r_multiple,
                        "shares_remaining": getattr(pos, "shares_remaining", 0.0),
                    },
                )

            # Telegram Alert (Enhanced for Sovereign Elite v2)
            from telegram_alerts import send_telegram_alert

            # Smart Metadata Recovery
            icon = "💰" if realized_net_pnl > 0 else "📉" if realized_net_pnl < 0 else "🛡️"
            intent = pos.meta.get("intent") or getattr(pos, "intent", "Sovereign")
            pattern_name = pos.meta.get("pattern") or pos.pattern or "Sovereign Signal"

            # Account ID Sanitization
            acc_id = pos.account_id
            if acc_id == "UNKNOWN":
                from config import IBKR_ACCOUNT_ID

                acc_id = IBKR_ACCOUNT_ID or "Master Account"

            # Reason Translation
            reason = exit_type.replace("_", " ").title()
            if "HEARTBEAT" in reason.upper():
                reason = "Sovereign Safety Veto"

            # Duration Formatting
            duration_min = (
                now
                - (
                    pos.entry_time
                    if pos.entry_time.tzinfo
                    else pos.entry_time.replace(tzinfo=timezone.utc)
                )
            ).total_seconds() / 60
            duration_str = (
                f"{duration_min:.1f}m" if duration_min < 60 else f"{duration_min / 60:.1f}h"
            )

            # Format detailed message
            title = "PARTIAL HARVEST" if exit_type == "PARTIAL" else "TRADE FINALIZED"
            outcome = (
                "PROFIT" if realized_net_pnl > 0
                else "LOSS" if realized_net_pnl < 0
                else "BREAKEVEN"
            )

            msg = (
                f"{icon} <b>{title}: {pos.symbol}</b>\n"
                f"<i>Account: {acc_id} ({pos.account_type.upper()})</i>\n"
                "───────────────────\n"
                f"<b>Size:</b> {abs(pos.qty):.0f} units\n"
                f"<b>Entry:</b> ${pos.entry_price:,.2f}\n"
                f"<b>Exit:</b>  ${pos.current_price:,.2f}\n"
                "───────────────────\n"
                f"<b>Strategy:</b> {intent}\n"
                f"<b>Pattern:</b> {pattern_name}\n"
                f"<b>Reason:</b> {reason}\n"
                "───────────────────\n"
                f"<b>Outcome:</b> {outcome}\n"
                f"<b>Net PnL:</b> <code>${realized_net_pnl:+.2f}</code>\n"
                f"<b>Efficiency:</b> {r_multiple:+.2f}R\n"
                f"<b>Duration:</b> {duration_str}\n"
                "───────────────────\n"
                f"<b>SESSION P&L:</b> <code>${self.session_pnl:+.2f}</code>"
            )
            await send_telegram_alert(msg)

        except Exception as e:
            logger.error(f"Failed to process exit for {pos.symbol}: {e}")
            self._exit_failure_count[symbol] = strikes + 1

    # HELPER METHODS

    async def _detect_regime(self) -> str:
        """Use Agent D's regime classifier with REAL market data from database."""
        try:
            vix = await self._get_vix()

            # Use the local SPY buffer for zero-latency momentum calculation.
            # This eliminates the NameError and avoids heavy SQL queries.
            momentum = 0.0
            spy_above_200ma = True
            if len(self.spy_buffer) >= 20:
                l_spy = list(self.spy_buffer)
                momentum = (l_spy[-1] - l_spy[-20]) / l_spy[-20] if l_spy[-20] != 0 else 0
                if len(l_spy) >= 200:
                    sma_200 = sum(l_spy) / 200
                    spy_above_200ma = l_spy[-1] > sma_200
            elif self.db_conn:
                # Fallback to DB (Legacy path) - Use 1d data for SMA 200
                try:
                    # Query 1d data for true 200-day moving average
                    spy_df = await asyncio.to_thread(
                        pd.read_sql_query,
                        "SELECT close FROM ohlcv WHERE symbol='SPY' AND timeframe='1d' "
                        "ORDER BY timestamp DESC LIMIT 250",
                        self.db_conn,
                    )
                    if not spy_df.empty:
                        # Re-sort to chronological order for mean calculation
                        closes = spy_df["close"].iloc[::-1].tolist()
                        if len(closes) >= 20:
                            momentum = (
                                (closes[-1] - closes[-20]) / closes[-20] if closes[-20] != 0 else 0
                            )
                        if len(closes) >= 200:
                            sma_200 = sum(closes[-200:]) / 200
                            spy_above_200ma = closes[-1] > sma_200
                            logger.debug(
                                f"True Daily SMA 200 detected: {sma_200:.2f} "
                                f"(Price: {closes[-1]:.2f})"
                            )
                except Exception as e:
                    logger.debug(f"Regime data fallback (1d): {e}")

            breadth = 0.55  # default
            if self.db_conn:

                def _sync_breadth() -> float:
                    try:
                        total = 0
                        positive = 0
                        major_indices = [
                            "SPY",
                            "QQQ",
                            "IWM",
                            "DIA",
                            "XLK",
                            "NVDA",
                            "MSFT",
                            "AAPL",
                            "TSLA",
                            "META",
                        ]

                        for sym in major_indices:
                            if sym in self.last_tick_prices:
                                total += 1
                                if sym in self.last_tick_prices:  # placeholder for trend check
                                    positive += 1
                            else:
                                # Fallback to DB
                                row = pd.read_sql_query(
                                    "SELECT close FROM ohlcv WHERE symbol=? "
                                    "ORDER BY timestamp DESC LIMIT 2",
                                    self.db_conn,
                                    params=(sym,),
                                )
                                if not row.empty and len(row) >= 2:
                                    total += 1
                                    if row["close"].iloc[0] > row["close"].iloc[1]:
                                        positive += 1
                        return positive / total if total > 0 else 0.55
                    except Exception:
                        return 0.55

                breadth = await asyncio.to_thread(_sync_breadth)

            regime = self.regime_classifier.classify(
                vix=vix,
                spy_above_200ma=spy_above_200ma,
                breadth=breadth,
                momentum=momentum,
            )
            logger.info(
                f"Regime: {regime} (VIX={vix:.1f}, Mom={momentum:.4f}, "
                f"Breadth={breadth:.2f}, SPY>200MA={spy_above_200ma})"
            )
            # PERSIST Context for the State Capsule
            self.session_restorer.save_cognitive_capsule(
                {
                    "regime": regime,
                    "conviction_state": self.conviction_state,
                    "session_pnl": self.session_pnl,
                    "session_stats": self.session_stats,
                    "timestamp": time.time_ns(),
                }
            )
            return regime
        except Exception:
            return "CHOPPY"

    async def _get_vix(self) -> float:
        """Get current VIX level from database (populated by data pipeline)."""

        def _sync_get_vix() -> float:
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    cursor.execute("SELECT value FROM vix_data ORDER BY timestamp DESC LIMIT 1")
                    row = cursor.fetchone()
                    cursor.close()
                    if row and row[0] is not None and float(row[0]) > 0:
                        vix_val = min(100.0, float(row[0]))
                        self._last_vix = vix_val
                        return vix_val
                return getattr(self, "_last_vix", 18.0)
            except Exception:
                return getattr(self, "_last_vix", 18.0)

        return await asyncio.to_thread(_sync_get_vix)  # type: ignore

    async def _get_watchlist(self) -> list[str]:
        """Get current watchlist from database or config."""
        # Expanded HFT High-Beta/High-Volume Watchlist
        return [
            # Core Indices
            "SPY",
            "QQQ",
            "IWM",
            "DIA",
            # Mag 7 & Trillion Dollar Tech
            "AAPL",
            "MSFT",
            "GOOGL",
            "AMZN",
            "NVDA",
            "META",
            "TSLA",
            # High Beta Semi / AI
            "AMD",
            "AVGO",
            "SMCI",
            "ARM",
            "MU",
            "PLTR",
            # Crypto Proxies
            "COIN",
            "MSTR",
            # Banks / Value
            "JPM",
            "GS",
            "V",
            "MA",
            # Retail / Consumers
            "WMT",
            "COST",
            "NFLX",
        ]

    def _is_market_open(self) -> bool:
        """Return True if NYSE is currently in the regular 9:30-16:00 ET session."""
        from zoneinfo import ZoneInfo

        if os.environ.get("FORCED_MARKET_OPEN") == "1":
            return True

        try:
            et_tz = ZoneInfo("America/New_York")
            now = datetime.now(et_tz)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
            market_open = dt_time(9, 30)
            market_close = dt_time(16, 0)
            return market_open <= now.time() <= market_close
        except Exception:
            return False

    async def _fetch_ohlcv(self, symbol: str) -> pl.DataFrame | pd.DataFrame | str | None:
        """
        Fetch OHLCV data for a symbol from the projection database.
        Returns:
            - pd.DataFrame  → usable rows found
            - "STALE"        → rows exist but are too old for the current session
            - None           → symbol has zero rows in DB (DataPipeline hasn't fetched it yet)
        """
        try:
            if not self.db_conn:
                return None

            # If we fetched this symbol within the last 5 seconds, return the cached copy.
            # This eliminates redundant DB queries during the 20Hz scan cycle.
            now_mono = time.monotonic()
            if symbol in self._hot_cache and (now_mono - self._hot_cache_time.get(symbol, 0)) < 5.0:
                return self._hot_cache[symbol]

            # QuestDB read path only when the shared adapter is active (same instance as pipeline)
            df_qdb = None

            # If QuestDB has timed out repeatedly, we 'Break the circuit' and skip it for 5 minutes.
            if self._qdb_circuit_broken and (now_mono - self._qdb_last_failure_time) < 300:
                pass  # Skip QuestDB and use SQLite/Cache fallback
            elif self.qdb.enabled:
                try:
                    from config import QUESTDB_CONNECT_TIMEOUT_SEC

                    df_qdb = await asyncio.wait_for(
                        self.qdb.fetch_ohlcv_pandas(symbol, timeframe="1m", limit=200),
                        timeout=QUESTDB_CONNECT_TIMEOUT_SEC,
                    )
                    # Success: Reset failure count
                    self._qdb_failure_count = 0
                except (asyncio.TimeoutError, TimeoutError):
                    self._qdb_failure_count += 1
                    self._qdb_last_failure_time = now_mono
                    if self._qdb_failure_count >= 3:
                        self._qdb_circuit_broken = True
                        logger.critical(
                            "QuestDB SLOWNESS DETECTED. Circuit Broken for 5 minutes. "
                            "Failing over to SQLite/Cache."
                        )
                    else:
                        logger.warning(
                            f"QuestDB timeout for {symbol} ({self._qdb_failure_count}/3) "
                            "— failing over to SQLite"
                        )
                    df_qdb = None
                except Exception as q_err:
                    logger.debug(f"QuestDB read error for {symbol}: {q_err}")
                    df_qdb = None

            use_fallback = True
            if df_qdb is not None:
                if not df_qdb.empty:
                    # Check if QuestDB data is stale
                    qdb_max_ts = pd.to_datetime(df_qdb["timestamp"], utc=True).max()
                    now_utc = pd.Timestamp.utcnow()
                    qdb_staleness = (now_utc - qdb_max_ts).total_seconds()

                    market_open = self._is_market_open()
                    staleness_limit = 1200 if market_open else 259200

                    if qdb_staleness <= staleness_limit:
                        use_fallback = False
                    else:
                        logger.debug(
                            f"QuestDB returned stale data for {symbol} "
                            f"({qdb_staleness / 60:.1f}m old), falling back to SQLite"
                        )

            if use_fallback:
                if self.qdb.enabled:
                    logger.debug(f"QuestDB returned empty for {symbol}, falling back to SQLite")
                query = (
                    "SELECT timestamp, open, high, low, close, volume "
                    "FROM ohlcv WHERE symbol=? AND timeframe='1m' "
                    "ORDER BY timestamp DESC LIMIT 200"
                )
                try:
                    df = await asyncio.wait_for(
                        asyncio.to_thread(pd.read_sql_query, query, self.db_conn, params=[symbol]),
                        timeout=30.0,
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    logger.warning(f"SQLite timeout for {symbol} after 15s — skipping symbol")
                    return None
            else:
                df = df_qdb

            # Final check with explicit narrowing to resolve Pyre2 NoneType errors
            if df is None:
                logger.warning(f"NO DATA: {symbol} — both QuestDB and SQLite returned None")
                return None

            df_frame: pd.DataFrame = cast(pd.DataFrame, df)
            if df_frame.empty:
                logger.warning(f"NO DATA: {symbol} — SQLite ohlcv table returned empty dataframe")
                return None

            # but all indicators and slicing ([-1]) expect ASCENDING chronological order.
            df_frame = df_frame.iloc[::-1].reset_index(drop=True)

            # Timestamps in DB are timezone-aware (e.g. "2026-04-02T10:56:00-04:00").
            # We must normalise BOTH sides to UTC before subtracting — stripping
            # tzinfo with tz_localize(None) is wrong because it discards the UTC
            # offset without adjusting the clock value, producing a ghost gap equal
            # to the UTC offset of the local machine (e.g. 4 h → 240 min, which
            # cascades into the observed ~2361 min false-stale signal).
            try:
                latest_bar_ts = pd.to_datetime(df_frame["timestamp"], utc=True).max()
                # Always compare in UTC; pd.Timestamp.utcnow() returns UTC-aware
                now_utc = pd.Timestamp.utcnow()

                staleness = (now_utc - latest_bar_ts).total_seconds()

                market_open = self._is_market_open()
                # Staleness gate check
                # 48 h when closed (covers weekday evenings + weekends without false
                # staleness rejections — prior session data is still valid for pre-scan).
                staleness_limit = 3600 if market_open else 259200

                if os.environ.get("FORCED_MARKET_OPEN") == "1":
                    staleness_limit = 1_000_000  # Allow very old data for sim

                if staleness > staleness_limit:
                    staleness_min = staleness / 60
                    if market_open:
                        logger.info(
                            f"STALE DATA: {symbol} newest bar is {staleness_min:.1f}min old "
                            f"(pipeline may be lagging or clock skew) — skipping"
                        )
                    else:
                        # Only log once every 4 hours per symbol to avoid spamming on weekends
                        last_alert = getattr(self, "_last_stale_alert", {})
                        now = time.time()
                        if now - last_alert.get(symbol, 0) > 14400:  # 4 hours
                            logger.warning(
                                f"STALE (MARKET CLOSED): {symbol} newest bar is "
                                f"{staleness_min:.0f}min old (>24h) — skipping"
                            )
                            last_alert[symbol] = now
                            self._last_stale_alert = last_alert
                    return cast(pd.DataFrame, "STALE")  # Sentinel — caller counts separately
                else:
                    logger.debug(
                        f"✓ FRESH DATA: {symbol} newest bar is {staleness / 60:.1f}min old "
                        "(passed staleness gate)"
                    )
            except Exception as e:
                logger.debug(f"Staleness check skipped for {symbol}: {e}")

            final_df = pl.from_pandas(df_frame)
            self._hot_cache[symbol] = final_df
            self._hot_cache_time[symbol] = time.monotonic()
            return final_df
        except Exception as e:
            import traceback

            logger.error(f"Error fetching OHLCV for {symbol}: {e}\n{traceback.format_exc()}")
            return None

    async def _restore_positions_from_db(self) -> None:
        """Restore OPEN positions from prior sessions and clean up orphans."""

        def _sync_restore() -> None:
            try:
                if not self.db_conn:
                    return
                cursor = self.db_conn.cursor()

                # 1. Find all OPEN trades
                cursor.execute(
                    "SELECT id, timestamp, instrument, entry_price, stop_price, target_price, "
                    "shares, r_r_ratio, pattern, regime, broker, account_id, trading_mode "
                    "FROM trades WHERE outcome = 'OPEN' ORDER BY id DESC"
                )
                rows = cursor.fetchall()
                if not rows:
                    logger.info("No orphaned OPEN positions found — clean start.")
                    cursor.close()
                    return

                restored = 0
                orphaned = 0
                seen_symbols: set = set()

                for row in rows:
                    (
                        tid,
                        ts_str,
                        symbol,
                        entry,
                        stop,
                        target,
                        qty,
                        rr,
                        pattern,
                        regime,
                        broker,
                        acc_id,
                        _tmode,
                    ) = row

                    # Parse entry time
                    try:
                        cleaned_ts = ts_str.replace("Z", "+00:00")
                        entry_time = datetime.fromisoformat(cleaned_ts)
                        if entry_time.tzinfo is None:
                            entry_time = entry_time.replace(tzinfo=timezone.utc)
                    except Exception:
                        entry_time = datetime.now(timezone.utc)

                    age_hours = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600

                    if age_hours > 720 or (symbol, broker) in seen_symbols:
                        cursor.execute(
                            "UPDATE trades SET outcome = 'ORPHANED', notes = ? WHERE id = ?",
                            (f"Orphaned on restart after {age_hours:.1f}h or duplicate", tid),
                        )
                        orphaned += 1
                        continue

                    # Restore as a live position
                    seen_symbols.add((symbol, broker))
                    pos = Position(
                        symbol=symbol,
                        qty=float(qty),
                        entry_price=float(entry),
                        entry_time=entry_time,
                        pattern=pattern or "Unknown",
                        initial_belief=0.50,
                        current_belief=0.50,
                        initial_stop=float(stop) if stop else float(entry) * 0.99,
                        stop_loss=float(stop) if stop else float(entry) * 0.99,
                        take_profit=float(target) if target else float(entry) * 1.02,
                        target_exit_time=datetime.now(timezone.utc) + timedelta(days=5),
                        trade_id=f"RESTORED-{tid}",
                        account_type=broker or "ibkr",
                        account_id=acc_id or "UNKNOWN",
                        catalyst_score=70.0,
                        dhatu_state="Restored",
                        regime_at_entry=regime or "UNKNOWN",
                        r_r_ratio=float(rr) if rr else 2.0,
                    )
                    self.positions.append(pos)
                    restored += 1

                self.db_conn.commit()
                cursor.close()

                if restored:
                    logger.info(
                        f" RESTORED {restored} position(s) from prior session: "
                        f"{[p.symbol for p in self.positions]}"
                    )
                if orphaned:
                    logger.info(f" Marked {orphaned} old/duplicate trade(s) as ORPHANED")

            except Exception as e:
                logger.error(f"Position restoration failed: {e}")

        await asyncio.to_thread(_sync_restore)  # type: ignore
        self._sanitize_positions()  # Pre-emptive purge before first cycle
        await self._reconcile_broker_positions()

    def _sanitize_positions(self):
        """Imperial Integrity Check: Purges non-object entries from memory pool."""
        valid = []
        for p in self.positions:
            if hasattr(p, "symbol") and not isinstance(p, dict):
                valid.append(p)
            elif isinstance(p, dict) and "symbol" in p:
                try:
                    from dataclasses import fields

                    from system_types import Position

                    field_names = {f.name for f in fields(Position)}
                    filtered = {k: v for k, v in p.items() if k in field_names}
                    valid.append(Position(**filtered))
                    logger.warning(f" SANITIZER: Re-hydrated dictionary for {p['symbol']}.")
                except Exception:
                    continue
        self.positions = valid

    async def _reconcile_broker_positions(self) -> None:
        """
        Sovereign Reconciliation Cycle: Dual-Broker Reality Handshake.
        Synchronizes internal memory with BOTH IBKR and MT5 realities.
        """
        try:
            # 1. Gather Reality from Brokers
            ibkr_reality = {}
            ibkr_polled = False
            if self.ibkr_conn and self.ibkr_conn.is_connected:
                ibkr_reality = self.ibkr_conn._positions_cache  # {symbol: qty}

                # SOVEREIGN GUARD: Force real-time poll if cache is empty OR seems incomplete
                # compared to our internal memory pool. This prevents 'Sync Lag' False Exits.
                memory_ibkr_count = len([p for p in self.positions if p.account_type == "ibkr"])
                if not ibkr_reality or len(ibkr_reality) < memory_ibkr_count:
                    logger.debug(
                        f" IBKR SYNC: Cache incomplete ({len(ibkr_reality)} vs "
                        f"{memory_ibkr_count}). Forcing reality poll..."
                    )
                    try:
                        positions_callable = getattr(self.ibkr_conn.ib, "positions", None)
                        if positions_callable is not None and callable(positions_callable):
                            actual_pos = await asyncio.to_thread(positions_callable)
                            # Clear and rebuild cache to ensure absolute accuracy
                            self.ibkr_conn._positions_cache.clear()
                            for p in actual_pos:
                                self.ibkr_conn._positions_cache[p.contract.symbol] = p.position
                            ibkr_reality = self.ibkr_conn._positions_cache
                            ibkr_polled = True
                    except Exception as sync_e:
                        logger.warning(f" IBKR SYNC: Reality poll failed: {sync_e}")

            mt5_reality = {}
            mt5_polled = False
            if self.mt5_conn and self.mt5_conn.is_connected:
                if hasattr(self.mt5_conn, "get_all_positions") and callable(
                    getattr(self.mt5_conn, "get_all_positions", None)
                ):
                    mt5_reality = await asyncio.to_thread(self.mt5_conn.get_all_positions)
                    mt5_polled = True
                else:
                    logger.warning(
                        "MT5 get_all_positions not callable, skipping MT5 reconciliation"
                    )

            # 2. Sanitize Memory
            self._sanitize_positions()

            # 3. Memory-to-Reality Mapping
            now_ts = datetime.now(timezone.utc)
            uptime = (
                (now_ts - self.start_time).total_seconds() if hasattr(self, "start_time") else 0.0
            )

            for p in list(self.positions):
                broker = p.account_type
                reality = ibkr_reality if broker == "ibkr" else mt5_reality
                polled = ibkr_polled if broker == "ibkr" else mt5_polled

                # SKEPTICAL HANDSHAKE: If symbol is missing from reality map, do NOT assume zero.
                if p.symbol not in reality:
                    # ONLY assume 0.0 if we just did a fresh, successful poll of the broker.
                    # Otherwise, it might be a temporary event lag (Sync Lag).
                    if not polled:
                        continue

                    _p_entry = (
                        p.entry_time
                        if p.entry_time.tzinfo
                        else p.entry_time.replace(tzinfo=timezone.utc)
                    )
                    age_seconds = (now_ts - _p_entry).total_seconds()

                    # Even with a poll, give young trades 2 minutes of grace for fill reflection
                    if age_seconds < 120:
                        continue
                    broker_qty = 0.0
                else:
                    broker_qty = reality[p.symbol]

                _p_entry = (
                    p.entry_time
                    if p.entry_time.tzinfo
                    else p.entry_time.replace(tzinfo=timezone.utc)
                )
                age_seconds = (now_ts - _p_entry).total_seconds()

                # A. The Zero-Sync Purge (Clean up phantom positions)
                # ONLY purge if: Uptime > 300s, Age > 300s (5m), and Reality is confirmed FLAT
                if uptime > 300 and age_seconds > 300 and abs(broker_qty) < 0.1:
                    logger.warning(
                        f" SYNC PURGE [{broker.upper()}]: {p.symbol} is flat in reality. "
                        "Removing from memory."
                    )
                    if p in self.positions:
                        self.positions.remove(p)
                    self._mark_trade_liquidated(p.symbol, broker)
                    continue

                # B. Quantity & Polarity Sync
                # Only sync if the symbol was FOUND in the reality map to prevent
                # zeroing-out during blips.
                if p.symbol in reality and abs(p.qty - broker_qty) > 0.00001:
                    if age_seconds > 60:  # 60s grace for fill reflection
                        p.qty = float(broker_qty)
                        self._update_trade_volume(p.symbol, broker, p.qty)

            # Triggers a high-visibility audit once per cycle (or on-demand)
            report_lines = [
                "\n" + "=" * 80,
                "   SOVEREIGN REALITY HANDSHAKE (Memory vs Broker) ",
                "=" * 80,
                f" {'Symbol':<10} | {'Broker':<8} | {'Memory Qty':<12} | "
                f"{'Reality Qty':<12} | {'Status':<10}",
                "-" * 80,
            ]

            all_symbols = (
                set(ibkr_reality.keys())
                | set(mt5_reality.keys())
                | {p.symbol for p in self.positions}
            )
            for sym in sorted(all_symbols):
                for b in ["ibkr", "mt5"]:
                    reality_map = ibkr_reality if b == "ibkr" else mt5_reality
                    if b == "mt5" and not (self.mt5_conn and self.mt5_conn.is_connected):
                        continue

                    m_pos = next(
                        (p for p in self.positions if p.symbol == sym and p.account_type == b), None
                    )
                    m_qty = m_pos.qty if m_pos else 0.0
                    r_qty = reality_map.get(sym, 0.0)

                    if abs(m_qty) < 0.01 and abs(r_qty) < 0.01:
                        continue

                    status = " MATCH" if abs(m_qty - r_qty) < 0.0001 else " DRIFT"
                    report_lines.append(
                        f" {sym:<10} | {b:<8} | {m_qty:<12.2f} | {r_qty:<12.2f} | {status}"
                    )

            report_lines.append("=" * 80 + "\n")
            logger.info("\n".join(report_lines))

            # 4. Adoption Protocol (Discover unmanaged positions)
            all_managed = {(p.symbol, p.account_type) for p in self.positions}

            # Adopt from IBKR
            for symbol, qty in ibkr_reality.items():
                if abs(qty) >= 0.1 and (symbol, "ibkr") not in all_managed:
                    await self._adopt_orphan(symbol, qty, "ibkr")

            # Adopt from MT5
            for symbol, qty in mt5_reality.items():
                if abs(qty) >= 0.01 and (symbol, "mt5") not in all_managed:
                    await self._adopt_orphan(symbol, qty, "mt5")

        except Exception as e:
            logger.error(f"Sovereign Reconciliation Failed: {e}", exc_info=True)

    async def _adopt_orphan(self, symbol: str, qty: float, broker: str) -> None:
        """Absorb an unmanaged broker position into the Matrix."""
        logger.warning(
            f" ORPHAN DETECTED [{broker.upper()}]: {symbol} | Qty: {qty}. Initiating Adoption..."
        )
        try:
            # 1. Get current price context
            price = self.last_tick_prices.get(symbol, 0.0)
            if price <= 0:
                market_data = await self._fetch_market_snapshot(symbol)
                price = market_data.get("price", 0.0) if market_data else 0.0

            direction = "LONG" if qty > 0 else "SHORT"

            # 2. Rehydrate from DB if exists
            db_row = None
            if self.db_conn:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "SELECT entry_price, stop_price, target_price FROM trades "
                    "WHERE instrument=? AND broker=? AND outcome='OPEN' ORDER BY id DESC LIMIT 1",
                    (symbol, broker),
                )
                db_row = cursor.fetchone()

            if db_row:
                entry, stop, target = db_row
                stop = stop or (entry * 0.98 if qty > 0 else entry * 1.02)
                target = target or (entry * 1.05 if qty > 0 else entry * 0.95)
            else:
                # Emergency Logic: tight defensive stop
                entry = price if price > 0 else 0.0
                stop = entry * 0.985 if qty > 0 else entry * 1.015
                target = entry * 1.10 if qty > 0 else entry * 0.90

            # 3. Construct Position
            from system_types import Position

            adopted = Position(
                symbol=symbol,
                qty=qty,
                entry_price=entry,
                entry_time=datetime.now(timezone.utc),
                pattern="ADOPTED_ORPHAN",
                stop_loss=stop,
                initial_stop=stop,
                take_profit=target,
                trade_id=f"ADOPTED-{broker.upper()}-{symbol}",
                account_type=broker,
                meta={"adoption_ts": time.time_ns()},
            )

            self.positions.append(adopted)

            # 4. Persistence
            if self.db_conn and not db_row:
                cursor = self.db_conn.cursor()
                cursor.execute(
                    "INSERT INTO trades (timestamp, instrument, direction, quantity, entry_price, "
                    "outcome, stop_price, target_price, broker, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        time.time_ns(),
                        symbol,
                        direction,
                        qty,
                        price,
                        "OPEN",
                        stop,
                        target,
                        broker,
                        "Sovereign Adoption Protocol v1.0-beta",
                    ),
                )
                adopted.db_id = cursor.lastrowid
                self.db_conn.commit()

            logger.info(f" ADOPTED: {symbol} in {broker.upper()} absorbed @ {price:.2f}")

            if (
                self.bus
                and hasattr(self.bus, "publish")
                and callable(getattr(self.bus, "publish", None))
            ):
                await self.bus.publish(
                    "notification.telegram",
                    {
                        "message": (
                            f" *ORPHAN ADOPTED*\nBroker: {broker.upper()}\n"
                            f"Symbol: {symbol}\nQty: {qty}\nStop: {stop:.2f}"
                        )
                    },
                )

        except Exception as e:
            logger.error(f"Failed to adopt orphan {symbol} on {broker}: {e}")

    def _mark_trade_liquidated(self, symbol: str, broker: str) -> None:
        """Update DB to reflect that a trade is no longer open."""
        try:
            if self.db_conn:
                self.db_conn.execute(
                    "UPDATE trades SET outcome = 'LIQUIDATED' WHERE instrument = ? "
                    "AND broker = ? AND outcome = 'OPEN'",
                    (symbol, broker),
                )
                self.db_conn.commit()
        except Exception as e:
            logger.debug(f"DB mark_liquidated failed for {symbol} on {broker}: {e}")

    def _update_trade_volume(self, symbol: str, broker: str, qty: float) -> None:
        """Update DB with actual volume from broker reality."""
        try:
            if self.db_conn:
                self.db_conn.execute(
                    "UPDATE trades SET shares = ? WHERE instrument = ? "
                    "AND broker = ? AND outcome = 'OPEN'",
                    (abs(qty), symbol, broker),
                )
                self.db_conn.commit()
        except Exception as e:
            logger.debug(f"DB update_trade_volume failed for {symbol} on {broker}: {e}")

    async def _fetch_market_snapshot(self, symbol: str) -> dict | None:
        """Get latest price, VIX, and breadth for Agent B evaluation."""
        try:
            snapshot = {
                "symbol": symbol,
                "price": None,  # Use None as sentinel for missing price
                "price_change_pct": 0.0,
                "vix": await self._get_vix(),
                "breadth": 0.55,  # Default
                "volume_ratio": 1.0,
                "momentum": 0.1,
            }

            # 0. HFT Replay Acceleration Layer
            if (
                hasattr(self, "_last_tick_price")
                and self._last_tick_price
                and symbol in self._last_tick_price
            ):
                snapshot["price"] = float(self._last_tick_price[symbol])
            elif symbol in self.last_tick_prices:
                snapshot["price"] = float(self.last_tick_prices[symbol])

            # 1. Fallback to latest price from OHLCV table if price is still None
            if snapshot["price"] is None:
                df = await self._fetch_ohlcv(symbol)  # type: ignore
                if df is not None and not isinstance(df, str) and len(df) > 0:
                    latest_close = float(df["close"][-1])
                    prev_close = float(df["close"][-2]) if len(df) > 1 else latest_close

                    snapshot["price"] = latest_close
                    snapshot["price_change_pct"] = (latest_close - prev_close) / (
                        prev_close + 1e-10
                    )

            return snapshot
        except Exception as e:
            logger.error(f"Error fetching market snapshot for {symbol}: {e}")
            return None

    async def get_safe_buying_power(self, account_type: str = "ibkr") -> float:
        """
        Defensive Equity Engine.
        Calculates buying power with a VIX-weighted volatility haircut.
        Ensures the sizer never sytems on 'hallucinated' equity during crashes.
        """
        raw_equity = await self._get_account_value(account_type, force_fresh=True)
        vix = await self._get_vix()

        # Volatility Haircut: 2% base + (VIX / 2.5)%
        # e.g., VIX 20 -> 10% Haircut | VIX 40 -> 18% Haircut
        haircut_pct = 0.02 + (vix / 250.0)
        safe_equity = raw_equity * (1.0 - haircut_pct)

        logger.debug(
            f"Defensive Equity: Raw ${raw_equity:.2f} | VIX {vix:.1f} | "
            f"Haircut {haircut_pct:.1%} | Safe ${safe_equity:.2f}"
        )
        return safe_equity

    async def _get_account_value(self, account_type: str, force_fresh: bool = False) -> float:
        """Get account equity value."""
        now = time.time()
        if not force_fresh and (now - self._last_account_value["timestamp"]) < 60.0:
            cached = self._last_account_value.get(account_type, 0.0)
            if cached > 0:
                return cached

        try:
            val = STARTING_CAPITAL_CAD
            if account_type == "ibkr" and self.ibkr_client:
                if hasattr(self.ibkr_client, "isConnected") and self.ibkr_client.isConnected():
                    # Priority: Use NetLiquidation to avoid currency confusion
                    acc_vals = self.ibkr_client.accountValues()
                    fallback_val = (
                        self.ibkr_drawdown.peak_equity
                        if hasattr(self, "ibkr_drawdown") and self.ibkr_drawdown.peak_equity > 0
                        else STARTING_CAPITAL_CAD
                    )
                    liq_vals = [float(x.value) for x in acc_vals if x.tag == "NetLiquidation"]
                    val = max(liq_vals) if liq_vals else fallback_val
            elif account_type == "mt5":
                import MetaTrader5 as mt5

                def _sync_mt5_account():
                    if not mt5.initialize():
                        return STARTING_CAPITAL_CAD
                    info = mt5.account_info()
                    return info.equity if info else STARTING_CAPITAL_CAD

                val = await asyncio.to_thread(_sync_mt5_account)

            # Update cache
            self._last_account_value[account_type] = val
            self._last_account_value["timestamp"] = now
            return val

        except Exception as e:
            logger.warning(f"Account check failed (non-fatal): {e}")
            return self._last_account_value.get(account_type, STARTING_CAPITAL_CAD)

    async def _get_daily_pnl(self, account_type: str) -> float:
        """Get today's P&L."""

        def _sync_daily_pnl() -> float:
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    cursor.execute(
                        "SELECT COALESCE(SUM(pnl_dollars), 0) FROM trades "
                        "WHERE timestamp LIKE ? AND broker = ?",
                        (f"{today}%", account_type),
                    )
                    result = cursor.fetchone()
                    cursor.close()
                    if result and result[0] is not None:
                        return float(result[0])
                return 0.0
            except Exception:
                return 0.0

        return await asyncio.to_thread(_sync_daily_pnl)

    async def _place_ibkr_order(
        self,
        symbol: str,
        direction: str,
        shares: float,
        urgency: str = "LOW",
        limit_price: float = 0.0,
        stop_price: float = 0.0,
        target_price: float = 0.0,
        **kwargs,
    ) -> str:
        """Helper to route orders through Agent C (IBKR)."""
        if not self.ibkr_conn:
            return ""

        # Prevent redundant exits for symbols already pending on the book.
        if await asyncio.to_thread(self.ibkr_conn.has_pending_order, symbol):
            logger.info(
                f"Sovereign Shield: Suppressed redundant order for {symbol} (Order Pending)."
            )
            return "SHIELDED"

        try:
            # Live query — touches the broker directly to be 100% sure
            broker_positions = {
                p.contract.symbol: p.position
                for p in self.ibkr_client.positions()
                if p.position != 0
            }
            broker_qty = broker_positions.get(symbol, 0)

            # If the signs differ or magnitude is way off, fix memory IMMEDIATELY.
            for p in self.positions:
                if p.symbol == symbol and (
                    np.sign(p.qty) != np.sign(broker_qty) or abs(p.qty - broker_qty) > 0.1
                ):
                    logger.warning(
                        f" MIRROR SYNC: {symbol} memory error ({p.qty}) "
                        f"corrected to Broker Reality ({broker_qty})."
                    )
                    p.qty = float(broker_qty)

            if direction == "SELL" and broker_qty < 0:
                logger.critical(
                    f" POLARITY SHIELD: Blocked SELL for {symbol} "
                    f"(Short exposure: {broker_qty}). Next cycle will BUY to close."
                )
                return None
            if direction == "BUY" and broker_qty > 0:
                logger.critical(
                    f" POLARITY SHIELD: Blocked BUY for {symbol} "
                    f"(Long exposure: {broker_qty}). Next cycle will SELL to close."
                )
                return None
        except Exception as guard_e:
            logger.debug(f"Polarity Guard Live Check skipped (Recovery mode active): {guard_e}")

        # IBKR Rate Limiting Protocol (Max 20/sec)
        await self.rate_limiter.acquire()

        try:
            if shares < 1:
                warn_msg = (
                    f" ZERO-SHARE SHIELD: Blocked {direction} for {symbol} (Size=0). "
                    "Check sizer math or Probe logic."
                )
                logger.warning(warn_msg)
                from telegram_alerts import send_telegram_alert

                await send_telegram_alert(
                    f" *SHIELD VETO: {symbol}*\n"
                    f"Action: Blocked {direction}\n"
                    f"Reason: Zero Size (Risk/Ladder restriction)\n"
                    f"Status: Standing Down"
                )
                return None

            # If we have stop/target geometry, we use the bracket executor
            if stop_price > 0 and target_price > 0:
                ok, reason = await asyncio.to_thread(
                    self.ibkr_conn.validate_order_pre_flight, symbol, direction, shares, limit_price
                )
                if not ok:
                    logger.critical(f" PRE-FLIGHT REJECTION for {symbol}: {reason}")
                    return None

                exec_token = self.ibkr_conn.generate_exec_token(symbol)
                kwargs["exec_token"] = exec_token

                ids = await self.ibkr_conn.place_bracket_order(
                    symbol=symbol,
                    direction=direction,
                    shares=shares,
                    limit_price=limit_price,
                    stop_loss=stop_price,
                    take_profit=target_price,
                    urgency=urgency,
                    **kwargs,  # Pass Ghost Expansion & Exec Token
                )
                return str(ids[0]) if ids else ""

            exec_token = self.ibkr_conn.generate_exec_token(symbol)
            kwargs["exec_token"] = exec_token

            if urgency == "EMERGENCY":
                # Force a true Market Order for safety flattens and heartbeat vetos.
                oid = await self.ibkr_conn.place_order(
                    symbol, direction, shares, order_type="MKT", **kwargs
                )
                if oid:
                    try:
                        self._order_submit_times[int(oid)] = datetime.now(timezone.utc)
                    except (ValueError, TypeError):
                        pass
                return oid

            if urgency == "LOW" and limit_price > 0:
                oid = await self.ibkr_conn.place_order(
                    symbol, direction, shares, order_type="LMT", limit_price=limit_price, **kwargs
                )
            else:
                oid = await self.ibkr_conn.place_order(
                    symbol, direction, shares, order_type="MKT", **kwargs
                )
            if oid:
                try:
                    self._order_submit_times[int(oid)] = datetime.now(timezone.utc)
                except (ValueError, TypeError):
                    pass
            return oid
        except Exception as e:
            logger.error(f"IBKR order failed: {e}")
            return None

    async def _update_drawdowns(self) -> None:
        """Update drawdown ladders from current account values."""
        ibkr_equity = await self._get_account_value("ibkr")
        self.ibkr_drawdown.update(ibkr_equity)
        if self.db_conn:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                ("last_heartbeat", time.time_ns()),
            )
            # Fix A: persist peak_equity so restore_peak_equity() can read it on restart
            cursor.execute(
                "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                ("peak_equity", str(self.ibkr_drawdown.peak_equity)),
            )
            self.db_conn.commit()
            cursor.close()

        # Checkpoint every 5 minutes to protect against Windows crashes
        # Throttled to ONCE per window to avoid slamming the disk
        now_ts = int(time.time())
        if now_ts % 300 < 60:
            last_freeze = getattr(self, "_last_freeze_time", 0)
            if now_ts - last_freeze > 60:
                self._last_freeze_time = now_ts
                state_to_freeze = {
                    "positions": self.positions,
                    "peak_equity": self.ibkr_drawdown.peak_equity,
                    "win_rates": self._learned_win_rates,
                    "session_stats": self.session_stats,
                }
                # Use to_thread to avoid blocking the event loop on Windows file I/O
                asyncio.create_task(
                    asyncio.to_thread(self.session_restorer.freeze_state, state_to_freeze)
                )

        mt5_equity = await self._get_account_value("mt5")
        self.prop_drawdown.update(mt5_equity)

    async def _log_signal(
        self, symbol: str, pattern: PatternResult, approved: bool, reason: str
    ) -> None:
        """Log signal to database (Shadow Portfolio tracking)."""

        def _sync_log() -> None:
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    cursor.execute(
                        "INSERT INTO signals (timestamp, instrument, pattern, base_quality, "
                        "catalyst_score, action_taken, skip_reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            time.time_ns(),
                            symbol,
                            pattern.name,
                            pattern.confidence,
                            pattern.confidence,
                            "APPROVED" if approved else "REJECTED",
                            reason,
                        ),
                    )
                    cursor.close()
            except Exception as e:
                logger.debug(f"Could not log signal: {e}")

        await asyncio.to_thread(_sync_log)  # type: ignore

    def _determine_target_broker(self) -> str:
        """Determines if the system should be in Equities (IBKR) or Forex (MT5) mode."""
        # April is EDT (UTC-4)
        now_utc = datetime.now(timezone.utc)
        now_ny = now_utc - timedelta(hours=4)
        hour = now_ny.hour
        minute = now_ny.minute

        # 16:00 - 17:00 NY: MAINTENANCE STAND-DOWN
        if hour == 16:
            logger.debug(
                f"Sovereign: Maintenance Window detected ({hour}:{minute:02d} NY). Standing down."
            )
            return "MAINTENANCE"

        # IBKR Equities: 9:30 AM - 4:00 PM NY
        if 9 <= hour < 16:
            if hour == 9 and minute < 30:
                return "MT5"  # Before Open
            return "IBKR"

        # MT5 Forex: 5:00 PM - 9:00 AM NY (Includes Asian/London sessions)
        return "MT5"

    async def _perform_broker_hotswap(self, target: str):
        """Swaps the system consciousness between brokers to save VRAM/CPU."""
        logger.warning(f" SOVEREIGN HOT-SWAP: Switching from {self.active_broker} to {target}...")

        if target == "MT5":
            # Shutdown IBKR streams if possible
            # (In this architecture, we keep connections but skip polling)
            self.active_broker = "MT5"
            # Initialize MT5
            # Vault.get MT5 credentials
            login = int(Vault.get("MT5_LOGIN", "0"))
            pw = Vault.get("MT5_PASSWORD", "")
            srv = Vault.get("MT5_SERVER", "")
            if login > 0:
                success = await asyncio.to_thread(self.mt5_conn.connect, login, pw, srv)
                if success:
                    logger.info("MT5: Connection established for Forex session.")
                else:
                    logger.error("MT5: Connection FAILED. Reverting to IBKR.")
                    self.active_broker = "IBKR"
        else:
            self.active_broker = "IBKR"
            logger.info("IBKR: Returning to Equities session.")

    async def _place_mt5_order(
        self, symbol, direction, shares, limit_price, stop_price, target_price, **kwargs
    ):
        """Forex Execution Engine for MT5."""
        logger.info(f"MT5: Placing {direction} order for {symbol} ({shares} lots)")

        risk_per_trade = getattr(self, "mt5_risk_per_trade", 10.0)

        lots = (
            self.mt5_sizer.calculate_lots(risk_per_trade, limit_price, stop_price, symbol) or 0.01
        )

        order_id = await asyncio.to_thread(
            self.mt5_conn.place_order,
            sym=symbol,
            dir=direction.lower(),
            vol=lots,
            sl=stop_price,
            tp=target_price,
        )
        return order_id

    async def _log_trade_entry(self, pos: Position) -> None:
        """Log trade entry to database."""

        def _sync_log() -> None:
            try:
                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    # Force absolute magnitude for the shares column to prevent
                    # 'Inverse' data corruption
                    # but keep the direction_str as the source of truth for side.
                    recorded_shares = abs(pos.qty)
                    direction_str = "LONG" if pos.qty > 0 else "SHORT"

                    # Record the 'Intelligence Profile' immediately so we don't forget if we crash.
                    intel_snap = json.dumps(
                        {
                            "lambda": getattr(self, "current_lambda", 0),
                            "regime": pos.regime_at_entry,
                            "vix": self.vix_data.get("VIX", 0) if hasattr(self, "vix_data") else 0,
                            "swarm_profile": getattr(
                                self.swarm_predictor, "_last_consensus", None
                            ).__dict__
                            if hasattr(self.swarm_predictor, "_last_consensus")
                            and self.swarm_predictor._last_consensus
                            else "None",
                        },
                        default=str,
                    )

                    outcome = str(getattr(pos, "status", "OPEN") or "OPEN")
                    broker = pos.account_type
                    account_id = pos.account_id or "UNKNOWN"
                    if outcome == "OPEN":
                        cursor.execute(
                            "SELECT id FROM trades WHERE instrument=? AND broker=? "
                            "AND account_id=? AND outcome='OPEN' ORDER BY id DESC LIMIT 1",
                            (pos.symbol, broker, account_id),
                        )
                        existing = cursor.fetchone()
                        if existing:
                            pos.db_id = existing[0]
                            logger.warning(
                                "Trade entry skipped for %s: existing OPEN trade id=%s on %s/%s",
                                pos.symbol,
                                pos.db_id,
                                broker,
                                account_id,
                            )
                            cursor.close()
                            return

                    cursor.execute(
                        "INSERT INTO trades (timestamp, instrument, direction, pattern, regime, "
                        "entry_price, stop_price, target_price, shares, r_r_ratio, catalyst_score, "
                        "dhatu_state, belief_at_entry, broker, account_id, trading_mode, outcome, "
                        "commission, slippage, net_pnl, intel_snapshot) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            pos.entry_time.isoformat(),
                            pos.symbol,
                            direction_str,
                            pos.pattern,
                            pos.regime_at_entry,
                            pos.entry_price,
                            pos.stop_loss,
                            pos.take_profit,
                            recorded_shares,
                            pos.r_r_ratio,
                            pos.catalyst_score,  # REMOVED ENCRYPTION FOR LEARNING ENGINE
                            pos.dhatu_state,
                            pos.initial_belief,  # REMOVED ENCRYPTION FOR LEARNING ENGINE
                            broker,
                            account_id,
                            self.mode,
                            outcome,
                            getattr(pos, "commission_cost", 0.0),
                            getattr(pos, "slippage_cost", 0.0),
                            0.0,
                            intel_snap,
                        ),
                    )
                    # Capture the RowID for precise exit tracking (Stop the Race Condition)
                    pos.db_id = cursor.lastrowid
                    self.db_conn.commit()
                    cursor.close()
            except Exception as e:
                logger.debug(f"Could not log trade entry: {e}")

        await asyncio.to_thread(_sync_log)  # type: ignore

    async def _log_trade_exit(
        self, pos: Position, exit_type: str, exit_price: float, pnl: float, r_multiple: float
    ) -> None:
        """Log trade exit to database and generate a post-mortem analysis."""

        def _sync_log() -> None:
            nonlocal exit_price, pnl
            try:
                # If exit_price is zero/none (Broker lag), recover from the Last Known Price
                # in pipeline
                if not exit_price or exit_price <= 0:
                    logger.warning(
                        f"GHOST RECOVERY: {pos.symbol} exit price is 0. "
                        "Pulling reality from pipeline..."
                    )
                    # Assume self.data_pipeline is available as we're in the Brain
                    if hasattr(self, "data_pipeline"):
                        last_tick = self.data_pipeline.get_last_price(pos.symbol)
                        if last_tick:
                            exit_price = last_tick
                            pnl = (exit_price - pos.entry_price) * pos.qty
                            logger.info(
                                f"Reality Restored: {pos.symbol} price set to ${exit_price:.2f}"
                            )

                if self.db_conn:
                    cursor = self.db_conn.cursor()
                    _entry_ts = (
                        pos.entry_time
                        if pos.entry_time.tzinfo
                        else pos.entry_time.replace(tzinfo=timezone.utc)
                    )
                    hold_hours = (datetime.now(timezone.utc) - _entry_ts).total_seconds() / 3600
                    cursor.execute(
                        "UPDATE trades SET exit_price=?, outcome=?, pnl_dollars=?, r_multiple=?, "
                        "hold_hours=?, belief_at_exit=?, net_pnl=? WHERE rowid=?",
                        (
                            exit_price,
                            exit_type,
                            pnl,  # Plaintext for Learning Engine
                            r_multiple,
                            hold_hours,
                            pos.current_belief,
                            pnl,  # Net Pnl Sync
                            getattr(pos, "db_id", 0),  # Use the specific ID
                        ),
                    )
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS performance_summary (
                            key TEXT PRIMARY KEY,
                            value TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("PRAGMA table_info(performance_summary)")
                    summary_cols = {row[1] for row in cursor.fetchall()}
                    if {"key", "value"}.issubset(summary_cols):
                        cursor.execute("""
                            SELECT
                                COUNT(*) AS closed_count,
                                SUM(CASE WHEN COALESCE(net_pnl, pnl_dollars, 0) > 0 THEN 1 ELSE 0 END) AS wins,
                                SUM(CASE WHEN COALESCE(net_pnl, pnl_dollars, 0) < 0 THEN 1 ELSE 0 END) AS losses,
                                SUM(COALESCE(net_pnl, pnl_dollars, 0)) AS net_pnl,
                                AVG(r_multiple) AS avg_r
                            FROM trades
                            WHERE outcome NOT IN ('OPEN', 'ORPHANED')
                        """)
                        row = cursor.fetchone()
                        closed_count = int(row[0] or 0)
                        wins = int(row[1] or 0)
                        losses = int(row[2] or 0)
                        summary = {
                            "closed_count": closed_count,
                            "wins": wins,
                            "losses": losses,
                            "win_rate": (wins / closed_count) if closed_count else 0.0,
                            "net_pnl": float(row[3] or 0.0),
                            "avg_r": float(row[4] or 0.0),
                            "updated_from": "brain._log_trade_exit",
                        }
                        cursor.execute(
                            "INSERT OR REPLACE INTO performance_summary (key, value, updated_at) "
                            "VALUES (?, ?, ?)",
                            ("latest", json.dumps(summary), datetime.now(timezone.utc)),
                        )
                    self.db_conn.commit()
                    cursor.close()
            except Exception as e:
                logger.debug(f"Could not log trade exit: {e}")

        # Trigger Pillar 4/6 (Wisdom & Skill Evolution)
        reasoning = (
            f"Exit Type: {exit_type} | PnL: ${pnl:.2f} | R-Multiple: {r_multiple:.2f}x | "
            f"Catalyst: {pos.catalyst_score:.1f}"
        )
        self.wisdom.write_post_mortem(pos, exit_type, pnl, reasoning)

        if pnl > 0:
            self.skill_tree.skills["pnl_to_next"] -= pnl
            if self.skill_tree.skills["pnl_to_next"] <= 0:
                self.skill_tree.unlock("stop-loss-adjustment")
                self.skill_tree.skills["pnl_to_next"] = 5000.0  # Next level
                logger.info("MATRIX LEVEL UP: Autonomy Level Increased (Tier 2).")

        self.skill_tree._save()  # Ensure skill point persistence

        self.loss_tracker.record_outcome(pnl > 0)
        if self.loss_tracker.consecutive_losses >= 5:
            logger.critical(" 5+ Consecutive Losses. Entering ABHAVA (Risk-Off) state.")
            self._oracle_dhatu = "Abhava"
        elif self.loss_tracker.win_streak >= 3:
            # We are in a groove, maintain or shift to Vriddhi
            if self._oracle_dhatu != "Vriddhi":
                logger.info(
                    f" WIN STREAK ({self.loss_tracker.win_streak}): Shifting to VRIDDHI state."
                )
                self._oracle_dhatu = "Vriddhi"

        await asyncio.to_thread(_sync_log)  # type: ignore

    async def _run_phantom_probe(self) -> None:
        """Sovereign Self-Test: Verify system wiring is 100% active."""
        await asyncio.sleep(60)  # Initial grace period
        while self.is_running:
            try:
                if hasattr(self, "coordinator"):
                    logger.info(" Brain: Initiating PHANTOM PROBE (System Wiring Check)...")
                    # Construct a fake proposal
                    from agent_a import PatternResult

                    fake_p = {
                        "symbol": "SPY",
                        "pattern": PatternResult(
                            name="PROBE_PULSE",
                            category="PROBE",
                            entry=500.0,
                            stop=495.0,
                            target=515.0,
                            confidence=99.0,  # Must be ≥60 (percentage scale) for Agent A to pass
                            r_r_ratio=3.0,
                            confirmed=True,
                            lambda_val=50,
                        ),
                        "timestamp": time.time_ns(),
                    }
                    # Run the probe (is_probe=True prevents actual execution)
                    success = await self.coordinator.initiate_trade_lifecycle(
                        "SPY", fake_p, is_probe=True
                    )
                    if not success:
                        logger.critical(
                            " PHANTOM PROBE FAILED! System logic returned False (Possible Quorum or Context Block). "
                            "Alerting via Telegram, but MAINTAINING system uptime."
                        )
                        if self.dms:
                            await self.dms._send_telegram_message(
                                " ⚠️ <b>[Sovereign Alert]</b>: Phantom Probe Failure. "
                                "System wiring check returned REJECT. "
                                "System is STAYING ONLINE but requires manual oversight."
                            )
            except Exception as e:
                logger.error(f"Phantom Probe Error: {e}")

            await asyncio.sleep(3600)  # Once per hour

    async def _background_conviction_sync(self) -> None:
        """
        SOLUTION 5: Asynchronous Prediction Pipeline.
        Continuously polls macro agents in the background to update the 'Global Conviction State'.
        This eliminates latency from the live trade-lifecycle quorum.
        """
        logger.info(" Brain: Asynchronous Prediction Pipeline ACTIVE (Background Thinking).")
        while self.is_running:
            try:
                # Construct Global Context (No symbol-specifics)
                global_ctx = {
                    "symbol": "GLOBAL",
                    "timestamp": time.time_ns(),
                    "regime": self.current_regime,
                    "account_value": await self._get_account_value("ibkr"),
                    "vix": await self._get_vix(),
                    "is_global_poll": True,
                }

                # Stage 2: Gated Intelligence (Atomic Parallelization with Watchdogs)
                from coordinator import TradingCoordinator

                now_iso = time.time_ns()
                new_convictions = {}

                logger.debug(f"Brain: Starting Conviction Sync for {now_iso}...")
                async with TradingCoordinator.get_neural_semaphore():
                    # 1. Oracle Poll
                    if self.dhatu_oracle:
                        logger.debug("Brain: Polling Dhatu_Oracle...")
                        try:
                            res = await asyncio.wait_for(
                                asyncio.to_thread(self.dhatu_oracle.evaluate_proposal, global_ctx),
                                timeout=20.0,
                            )
                            res["timestamp"] = now_iso
                            new_convictions["Dhatu_Oracle"] = res
                            logger.debug("Brain: Dhatu_Oracle synchronized.")
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.warning(
                                f"Brain: Dhatu_Oracle sync latency/error: {type(e).__name__}"
                            )

                    # 2. Swarm Poll
                    if self.swarm_predictor:
                        logger.debug("Brain: Polling Swarm_Predictor...")
                        try:
                            res = await asyncio.wait_for(
                                self.swarm_predictor.evaluate_proposal(global_ctx), timeout=60.0
                            )
                            res["timestamp"] = now_iso
                            new_convictions["Swarm_Predictor"] = res
                            logger.debug("Brain: Swarm_Predictor synchronized.")
                        except (asyncio.TimeoutError, Exception) as e:
                            import traceback

                            logger.warning(
                                f"Brain: Swarm_Predictor sync latency/error: "
                                f"{type(e).__name__}\n{traceback.format_exc()}"
                            )

                    # 3. Ultrathink Poll
                    if self.mind_ultrathink:
                        logger.debug("Brain: Polling Mind_Ultrathink...")
                        try:
                            res = await asyncio.wait_for(
                                self.mind_ultrathink.evaluate_proposal(global_ctx), timeout=20.0
                            )
                            res["timestamp"] = now_iso
                            new_convictions["Mind_Ultrathink"] = res
                            logger.debug("Brain: Mind_Ultrathink synchronized.")
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.warning(
                                f"Brain: Mind_Ultrathink sync latency/error: {type(e).__name__}"
                            )

                # ATOMIC UPDATE: Merge results into state in one go to prevent
                # mid-cycle hallucinations
                if new_convictions:
                    self.conviction_state.update(new_convictions)
                    logger.info(
                        " TradingBrain: Global Conviction State synchronized "
                        f"({len(new_convictions)} agents)."
                    )
                else:
                    logger.warning(
                        " TradingBrain: Conviction sync cycle finished with ZERO agents."
                    )

            except Exception as e:
                logger.error(f"Conviction Sync Error: {e}")

            # Update every 60 seconds (Cognitive Refresh Rate)
            await asyncio.sleep(60)

    async def _panic_liquidate_all(self) -> None:
        """Sovereign Shield: Emergency Total Portfolio Liquidation Sequence."""
        try:
            # 1. Access Agent C
            if hasattr(self.coordinator, "agents") and "agent_c_ibkr" in self.coordinator.agents:
                agent = self.coordinator.agents["agent_c_ibkr"]

                # Directly get positions from IB
                import ib_insync

                if hasattr(agent, "ib") and agent.ib.isConnected():
                    positions = agent.ib.positions()
                    if not positions:
                        logger.info(" SHIELD: No positions to liquidate. Clean Slate.")
                        return

                    logger.critical(f" SHIELD: Liquidating {len(positions)} positions immediately.")
                    for p in positions:
                        contract = p.contract
                        qty = p.position
                        action = "SELL" if qty > 0 else "BUY"
                        abs_qty = abs(qty)

                        logger.warning(f" SHIELD: Closing {contract.symbol} ({action} {abs_qty})")
                        order = ib_insync.MarketOrder(action, abs_qty)
                        agent.ib.placeOrder(contract, order)

                    logger.info(" SHIELD: Liquidation orders broadcast. Waiting for sync...")
                    await asyncio.sleep(5)
                    logger.critical(" SOVEREIGN SHIELD: TOTAL LIQUIDATION COMPLETE.")
        except Exception as e:
            logger.error(f"SHIELD: Panic Liquidation Failed: {e}")

    async def get_system_stats(self) -> dict[str, Any]:
        """PILLAR 6: System Telemetry Synthesis."""
        return {
            "session_pnl": self.session_pnl,
            "session_stats": self.session_stats,
            "open_positions": len(self.positions),
            "current_regime": getattr(self, "current_regime", "CHOPPY"),
            "dhatu_state": self._oracle_dhatu,
            "is_halted": self.emergency_halted,
            "last_scan_cycle": self.last_scan_stats.get("cycle", 0)
            if hasattr(self, "last_scan_stats")
            else 0,
        }

    async def stop(self) -> None:
        """Graceful shutdown."""
        logger.info("Stopping Trading Brain...")
        self.is_running = False

        if hasattr(self, "mind_observer") and self.mind_observer:
            try:
                self.mind_observer.stop()
            except Exception as e:
                logger.error(f"Error stopping mind_observer: {e}")

        # Parallel Task Cancellation
        tasks_to_cancel = [
            ("_bus_task", "Bus Listener"),
            ("_learner_task", "Live Learner"),
            ("_watchdog_task", "Watchdog"),
            ("_evolution_task", "Evolution Manager"),
            ("_main_task", "Main Loop"),
            ("_mind_task", "Trader Mind"),
            ("_phantom_probe_task", "Phantom Probe"),
            ("_conviction_task", "Conviction Sync"),
            ("_freezer_task", "Periodic Freeze"),
        ]

        cancel_tasks = []
        for attr, name in tasks_to_cancel:
            task = getattr(self, attr, None)
            if task and not task.done():
                logger.info(f"Cancelling TradingBrain task: {name}")
                task.cancel()
                cancel_tasks.append(task)

        if cancel_tasks:
            try:
                # Wait for all cancellations in parallel with a shared timeout
                await asyncio.wait_for(
                    asyncio.gather(*cancel_tasks, return_exceptions=True), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("TradingBrain: Some tasks failed to cancel within 5s.")
            except Exception as e:
                logger.error(f"Error during parallel task cancellation: {e}")

        # Stop component-specific minds
        minds = [
            "mind_architect",
            "mind_evolution",
            "mind_observer",
            "mind_experiment",
            "mind_ultrathink",
            "mind_system",
            "mind_ghost",
            "mind_math",
        ]
        for mind_attr in minds:
            mind = getattr(self, mind_attr, None)
            if mind and hasattr(mind, "stop"):
                try:
                    if asyncio.iscoroutinefunction(mind.stop):
                        await mind.stop()
                    else:
                        mind.stop()
                except Exception as e:
                    logger.error(f"Error stopping {mind_attr}: {e}")

        await self.qdb.stop()
        logger.info("Trading Brain stopped.")
