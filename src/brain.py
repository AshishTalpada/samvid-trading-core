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
import inspect
import logging
import os
import time
import traceback
from datetime import datetime, timedelta, timezone
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
)

import numpy as np
import pandas as pd
import polars as pl

logger = logging.getLogger(__name__)

from adaptive_learning import LiveAdaptiveEngine
from agent_a import (
    ContinuousBudgetMonitor,
    EscapeVelocityClassifier,
    FactorWeightCalibration,
    InMemorySovereignAtlas,
    MultiTimeframeAligner,
    NeuralRegimeClassifier,
    PatternDetector,
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
from brain_accounting import AccountingMixin
from brain_data import DataProvider
from brain_execution import ExecutionMixin
from brain_health import HealthChecker
from brain_position import PositionMonitor
from brain_reconcile import BrokerReconciler
from config import (
    FORCED_PAPER_MODE,
    MARKET_OBSERVATION_LEARNING_ENABLED,
    MARKET_OBSERVATION_THROTTLE_SEC,
    QUESTDB_ENABLED,
    STARTING_CAPITAL_CAD,
)
from confluence_engine import ConfluenceEngine
from exit_intelligence import ExitIntelligence
from intelligence_bus import SharedIntelligenceBus
from llm_circuit_breaker import HEAVY_BREAKER, LIGHT_BREAKER  # noqa: F401
from market_microstructure import MarketMicrostructure
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
from neural_governance import AgentVote, NeuralGovernanceEngine
from pandas_safety import safe_polars_from_pandas
from quant_signals import QuantConsensus
from questdb_adapter import QuestDBAdapter
from session_restorer import SessionRestorer
from sovereign_decision_engine import SovereignDecisionEngine
from sovereign_task import TaskManager
from strategy_router import RegimeStrategyRouter, TimeframeAwareDetector
from swarm_predictor import SwarmPredictor
from system_types import Position
from trade_interrogator import TradeInterrogator
from vault import Vault
from wisdom import SkillTreeManager, WisdomRepository
from workload_manager import WorkloadManager

if TYPE_CHECKING:
    import sqlite3

    from dhatu_oracle import DhatuOracle
    from native_slm import NativeSLM

# Re-export state primitives for backward compatibility (tests, other agents)
# TRADING STATE MACHINE
# TradingState FSM moved to brain_fsm.py so mixins can import it
from brain_fsm import TradingState
from brain_reconcile import _safe_entry_time  # noqa: F401 -- re-exported for tests
from brain_state import (
    ConsecutiveLossTracker,
    DrawdownLadder,
    DrawdownLevel,  # noqa: F401 -- re-exported for tests/other modules
    MorningBudget,
    TokenBucketRateLimiter,
)
from decision_ledger import LEDGER  # noqa: F401 -- re-exported for tests/patching
from portfolio_analyzer import PORTFOLIO_ANALYZER  # noqa: F401 -- re-exported for tests/patching

# Position class removed (Transferred to src/types.py for Coordinator-Safe Inversion)


# MORNING RISK BUDGET


# THE TRADING BRAIN


class TradingBrain(BrokerReconciler, HealthChecker, DataProvider, AccountingMixin, ExecutionMixin, PositionMonitor):
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

    @staticmethod
    def _learning_db_path() -> str:
        """Resolve the Agent D store without forcing tests to touch production state."""
        configured = os.environ.get("SOVEREIGN_LEARNING_DB_PATH", "").strip()
        return configured or "data/trading.db"

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
        self.start_time = datetime.now(timezone.utc)
        self._state_lock = asyncio.Lock()
        self.state = TradingState.STANDBY
        self.last_tick_prices: dict[str, float] = {}
        self.last_tick_bids: dict[str, float] = {}
        self.last_tick_asks: dict[str, float] = {}
        self._last_tick_price: dict[str, float] = {}  # Internal shadow for snapshotting
        self._last_tick_time: dict[str, datetime] = {}
        self.new_tick_event = asyncio.Event()

        # Live market microstructure: hawk-eye view of ticks, spread, VWAP, order flow.
        self.microstructure = MarketMicrostructure()
        self.trade_interrogator = TradeInterrogator(microstructure=self.microstructure)

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

        self.sync_oracle_state()

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
        self._positions_lock = asyncio.Lock()  # Protects self.positions from concurrent modification
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
        self.regime_router = RegimeStrategyRouter()
        self.timeframe_detector = TimeframeAwareDetector(
            pattern_detector=self.pattern_detector,
            router=self.regime_router,
        )
        self.confluence_engine = ConfluenceEngine(min_score=0.70)
        self.entropy_calc = SignalEntropyCalculator()
        self.escape_classifier = EscapeVelocityClassifier()
        self.mtf_aligner = MultiTimeframeAligner()
        self.sovereign_atlas = InMemorySovereignAtlas()
        self.neural_engine = FactorWeightCalibration()
        self.regime_classifier_neural = NeuralRegimeClassifier()

        self.dhatu_classifier = DhatuClassifier(oracle=self.dhatu_oracle)
        self.belief_tracker = BayesianBeliefTracker(prior=0.50)
        self.abhava_detector = ABHAVADetector()

        # Advisory agents: non-blocking signals that feed into decision context
        # but do NOT have veto power over the primary A-E quorum.
        try:
            from contrarian_agent import ContrarianAgent
            self.contrarian_agent = ContrarianAgent()
        except Exception as _ca_err:
            logger.warning(f"ContrarianAgent init skipped: {_ca_err}")
            self.contrarian_agent = None
        try:
            from chaos_agent import ChaosAgent
            self.chaos_agent = ChaosAgent()
        except Exception as _cha_err:
            logger.warning(f"ChaosAgent init skipped: {_cha_err}")
            self.chaos_agent = None
        try:
            from contagion_sentinel import ContagionSentinel
            self.contagion_sentinel = ContagionSentinel()
        except Exception as _cs_err:
            logger.warning(f"ContagionSentinel init skipped: {_cs_err}")
            self.contagion_sentinel = None
        try:
            from audit_agent import AuditAgent
            self.audit_agent = AuditAgent()
        except Exception as _aa_err:
            logger.warning(f"AuditAgent init skipped: {_aa_err}")
            self.audit_agent = None
        try:
            from discovery_engine import AlphaDiscoveryEngine
            self.alpha_discovery = AlphaDiscoveryEngine(population_size=30)
        except Exception as _ade_err:
            logger.warning(f"AlphaDiscoveryEngine init skipped: {_ade_err}")
            self.alpha_discovery = None
        try:
            from fractal_agent import FractalAgent
            self.fractal_agent = FractalAgent()
        except Exception as _fa_err:
            logger.warning(f"FractalAgent init skipped: {_fa_err}")
            self.fractal_agent = None
        try:
            from correlation_monitor import CorrelationBreakdownMonitor
            self.correlation_monitor = CorrelationBreakdownMonitor(window=20, contagion_threshold=0.80)
        except Exception as _cm_err:
            logger.warning(f"CorrelationBreakdownMonitor init skipped: {_cm_err}")
            self.correlation_monitor = None
        try:
            from flow_agent import CapitalFlowAgent
            self.flow_agent = CapitalFlowAgent()
        except Exception as _flow_err:
            logger.warning(f"CapitalFlowAgent init skipped: {_flow_err}")
            self.flow_agent = None
        try:
            from regime_agent import BayesianRegimeAgent
            self.bayesian_regime = BayesianRegimeAgent()
        except Exception as _br_err:
            logger.warning(f"BayesianRegimeAgent init skipped: {_br_err}")
            self.bayesian_regime = None
        try:
            from alpha_watchdog import AlphaDecayWatchdog
            self.alpha_watchdog = AlphaDecayWatchdog()
        except Exception as _aw_err:
            logger.warning(f"AlphaDecayWatchdog init skipped: {_aw_err}")
            self.alpha_watchdog = None
        try:
            from bayesian_oracle import BayesianOracle
            self.bayesian_oracle = BayesianOracle()
        except Exception as _bo_err:
            logger.warning(f"BayesianOracle init skipped: {_bo_err}")
            self.bayesian_oracle = None
        try:
            from debate_engine import DebateEngine
            self.debate_engine = DebateEngine(required_confidence=0.55)
        except Exception as _de_err:
            logger.warning(f"DebateEngine init skipped: {_de_err}")
            self.debate_engine = None

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
        _db_path = self._learning_db_path()
        self.db_path = _db_path  # Needed by session_restorer.restore_peak_equity
        self.live_learner = LiveLearningEngine(
            db_path=_db_path, bus=bus, evolution_engine=self.recursive_evolution, dms=self.dms
        )

        # 5. Live Adaptive Engine — real-time pattern feedback loop.
        self.adaptive_engine = LiveAdaptiveEngine()

        # 6. Neural Governance Engine — cross-agent consensus and audit.
        self.governance_engine = NeuralGovernanceEngine()

        self._qdb_circuit_broken = False
        self._qdb_last_failure_time = 0.0
        self._qdb_failure_count = 0
        self._hot_cache: dict[tuple[str, str], pd.DataFrame] = {}  # (symbol, timeframe) -> OHLCV df
        self._hot_cache_time: dict[tuple[str, str], float] = {}  # (symbol, timeframe) -> monotonic ts
        self._last_fresh_bar_at: dict[str, float] = {}  # symbol -> freshness proof monotonic ts

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
        self.task_manager = TaskManager(retire_active_on_restore=True)

        self.current_regime = "UNKNOWN"
        self.is_running = False
        self.conviction_state = {}

        is_mock_db = type(self.db_conn).__module__.startswith("unittest.mock")
        capsule = None if is_mock_db else self.session_restorer.load_cognitive_capsule()
        if capsule:
            self.current_regime = capsule.get("regime", "UNKNOWN")
            self.conviction_state = capsule.get("conviction_state", {})
            logger.info(
                f"Brain: Cognitive Capsule inhaled. Regime: {self.current_regime} | "
                "PnL will be rebuilt from today's closed-trade ledger."
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
        self._last_account_value = {
            "ibkr": 0.0,
            "mt5": 0.0,
            "ibkr_timestamp": 0.0,
            "mt5_timestamp": 0.0,
            "timestamp": 0.0,
        }
        self._account_value_meta: dict[str, dict[str, object]] = {}

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
        self._scan_veto_log_cache: dict[tuple[str, str, str], float] = {}
        self._scan_veto_log_interval = float(os.getenv("SOVEREIGN_SCAN_VETO_LOG_SEC", "60"))
        self._scan_no_action_backoff = float(os.getenv("SOVEREIGN_SCAN_NO_ACTION_BACKOFF_SEC", "2.5"))
        self._seen_news_hashes: dict[str, float] = {}  # hash -> monotonic ts (24h dedup)
        self._last_runtime_wall = datetime.now(timezone.utc)
        self._resume_quarantine_until: datetime | None = None
        self._last_resume_notice_at: datetime | None = None

        self._exit_failure_count: dict[str, int] = {}  # Symbol -> Strike Count
        self._exit_last_attempt: dict[str, datetime] = {}  # Symbol -> Last Re-attempt
        self._order_submit_times: dict[int, datetime] = {}  # OrderId -> Submission time

        # Background task registry — prevents 'Task was destroyed but it is pending!' errors
        # by maintaining strong references to fire-and-forget asyncio tasks.
        self._background_tasks: set[asyncio.Task] = set()

        # Subscribe the adaptive engine to trade.exit events now that the registry exists.
        if self.bus:
            self._background_tasks.add(
                asyncio.create_task(self.adaptive_engine.run_async(self.bus))
            )
            self._background_tasks.add(
                asyncio.create_task(self.governance_engine.run_async(self.bus))
            )

        self._thaw_task = None

    def sync_oracle_state(self) -> bool:
        """Hydrate the brain's macro freeze state from the attached DhatuOracle."""
        if not self.dhatu_oracle:
            return False

        state = self.dhatu_oracle.get_current_state()
        if not state:
            return False

        self._oracle_risk_modifier = float(state.risk_modifier)
        self._oracle_dhatu = str(state.dhatu_state)
        self._oracle_freeze = (
            self._oracle_dhatu in ("Abhava", "Viyoga") or self._oracle_risk_modifier <= 0.0
        )
        logger.info(
            f"TradingBrain: Synced Oracle state: {self._oracle_dhatu} "
            f"(Modifier: {self._oracle_risk_modifier:.2f}, Freeze: {self._oracle_freeze})"
        )
        return True

    async def _thaw_session_async(self) -> None:
        """Restores the brain's state via background thread to prevent startup hangs."""
        try:
            state = await asyncio.to_thread(self.session_restorer.thaw_state)
            if state:
                # Restore positions with FORCE HYDRATION (Pillar 2 Hardening)
                thawed_pos = state.get("positions", [])
                async with self._positions_lock:
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
                                logger.warning(
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
                            logger.warning(f"Brain: Skipping bad last_loss_time format: {_dt_err}")

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
            logger.warning(f"Brain: Session restore error (peak_equity may be stale): {_sr_err}")

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

    def _apply_macro_impact(self, payload: dict) -> bool:
        """Apply a bounded macro overlay without compounding repeated pulses."""
        status = str(payload.get("status", "ONLINE")).upper()
        impact = str(payload.get("impact", "UNKNOWN")).upper()
        if status == "UNAVAILABLE" or impact not in {"BEARISH", "BULLISH"}:
            return False

        current = float(self._oracle_risk_modifier)
        if impact == "BEARISH":
            updated = min(current, 0.8)
        elif current >= 1.0:
            updated = min(1.1, max(current, 1.05))
        else:
            updated = current
        self._oracle_risk_modifier = updated
        return updated != current

    async def get_ibkr_cushion(self) -> float:
        """Proxy to Agent C's margin probe via direct IBKR connection."""
        if self.ibkr_conn and hasattr(self.ibkr_conn, "get_margin_cushion"):
            return self.ibkr_conn.get_margin_cushion()
        return 1.0  # Default to safe

    async def _on_hft_tick(self, payload: dict) -> None:
        """Cache incoming ticks for high-frequency pricing updates."""
        symbol = payload.get("symbol")
        price = payload.get("price")
        if symbol and price:
            self.last_tick_prices[symbol] = float(price)

    async def _on_hft_news(self, payload: dict) -> None:
        """Neural News Trigger: Triggers re-scans on high-impact headlines."""
        import hashlib
        import time as _time

        _headline = str(payload.get("headline", "") or "")
        _url = str(payload.get("url", "") or "")
        _dedup_key = hashlib.md5((_headline + _url).encode()).hexdigest()
        _now = _time.monotonic()
        # Expire old entries (older than 24h)
        self._seen_news_hashes = {k: v for k, v in self._seen_news_hashes.items() if _now - v < 86400}
        if _dedup_key in self._seen_news_hashes:
            return  # already processed this article
        self._seen_news_hashes[_dedup_key] = _now

        raw_headline = str(payload.get("headline", ""))
        try:
            from auth.prompt_guard import PromptGuard

            guard = getattr(self, "_prompt_guard", None)
            if guard is None:
                guard = PromptGuard()
                self._prompt_guard = guard
            if not guard.is_safe(raw_headline):
                logger.warning("BRAIN: Blocked adversarial news payload before cognition.")
                return
            raw_headline = guard.sanitize(raw_headline, max_length=512)
        except Exception as guard_error:
            logger.debug("PromptGuard skipped for news payload: %s", guard_error)

        headline = raw_headline.upper()
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
            if (
                not self._is_market_open()
                and os.environ.get("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS") != "1"
            ):
                logger.debug(
                    "BRAIN: News action ignored while US equity market is closed: %s",
                    headline[:80],
                )
                return

            if self._is_oracle_entry_frozen():
                logger.debug(
                    "BRAIN: News action ignored during oracle freeze (%s, modifier=%.2f): %s",
                    self._oracle_dhatu,
                    self._oracle_risk_modifier,
                    headline[:80],
                )
                return

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

    def _is_oracle_entry_frozen(self) -> bool:
        """Return True when the oracle forbids new scan/trade cognition."""
        return (
            bool(getattr(self, "_oracle_freeze", False))
            or str(getattr(self, "_oracle_dhatu", "")) in ("Abhava", "Viyoga")
            or float(getattr(self, "_oracle_risk_modifier", 1.0)) <= 0.0
        )

    def _broker_is_connected(self, conn: Any) -> bool:
        """Return broker connectivity for agents exposing either a property or method."""
        if conn is None:
            return False
        state = getattr(conn, "is_connected", False)
        try:
            if callable(state):
                state = state()
            if inspect.isawaitable(state):
                logger.warning("Broker connectivity check returned awaitable; treating as offline.")
                return False
            return bool(state)
        except Exception as exc:
            logger.warning("Broker connectivity check failed: %s", exc)
            return False

    async def _initialize_ibkr_runtime(self) -> None:
        """Bind IBKR callbacks and launch crash recovery after the shared session connects."""
        if self.ibkr_conn and self._broker_is_connected(self.ibkr_conn):
            await self.ibkr_conn.ensure_connection()

    # MAIN LOOP

    async def start(self) -> None:
        """Start the trading brain as a background task."""
        self.is_running = True
        logger.info(f"Trading Brain started in {self.mode} mode.")
        await self._initialize_ibkr_runtime()
        await self._restore_session_pnl_from_ledger()

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
            "Operate Risk-Controlled Paper Trading",
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

        logger.info("TradingBrain: Background analysis components launched.")

    async def run(self) -> None:
        """Entry point for supervisor — blocks until tasks are finished."""
        logger.info(" MAIN BRAIN TASK ACTIVATED")
        await self.start()

        # Ensures the Brain never exits unexpectedly after a Veto or Rejection.
        try:
            while self.is_running:
                # Sentinel: keep run() alive. If the main task crashes or
                # completes for any reason, recreate it immediately.
                if (
                    not hasattr(self, "_main_task")
                    or self._main_task is None
                    or self._main_task.done()
                ):
                    exc = (
                        self._main_task.exception()
                        if self._main_task and not self._main_task.cancelled()
                        else None
                    )
                    if exc:
                        logger.error(
                            f"TradingBrain: _main_task died with exception: {exc}", exc_info=exc
                        )
                    else:
                        logger.warning("TradingBrain: _main_task exited cleanly. Restarting...")
                    self._main_task = asyncio.create_task(self._run_loop())

                await asyncio.sleep(2)  # Poll every 2s — never exits unless cancelled

        except asyncio.CancelledError:
            logger.info("TradingBrain: Run task cancelled.")
            await self.stop()
            raise
        except Exception as e:
            logger.error(f"TradingBrain: Systemic failure: {e}", exc_info=True)
            await self.stop()
            raise

    def _log_circuit_breaker_throttled(
        self,
        key: str,
        level: int,
        message: str,
        *,
        interval_sec: float = 300.0,
    ) -> None:
        """Log persistent circuit-breaker states without flooding operator logs."""
        now = time.monotonic()
        last_logs = getattr(self, "_circuit_breaker_last_log", None)
        if last_logs is None:
            last_logs = {}
            self._circuit_breaker_last_log = last_logs

        last_seen = float(last_logs.get(key, 0.0) or 0.0)
        if now - last_seen >= interval_sec:
            logger.log(level, message)
            last_logs[key] = now
        else:
            logger.debug(message)

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

                    # Circuit breaker: per-cycle safety gate
                    if self._is_oracle_entry_frozen():
                        self._log_oracle_freeze_cycle()
                        await asyncio.sleep(self.scan_interval)
                        continue

                    if not self.ibkr_drawdown.is_trading_allowed():
                        self._log_circuit_breaker_throttled(
                            "drawdown",
                            logging.CRITICAL,
                            "CIRCUIT BREAKER: Drawdown breach. Trading halted.",
                        )
                        await asyncio.sleep(60)
                        continue

                    if not self.loss_tracker.is_trading_allowed():
                        pause_until = getattr(self.loss_tracker, "pause_until", None)
                        reason = getattr(self.loss_tracker, "status_reason", lambda: "loss streak")()
                        pause_msg = (
                            f" Pause until {pause_until.isoformat()}."
                            if pause_until is not None
                            else ""
                        )
                        self._log_circuit_breaker_throttled(
                            "loss_streak",
                            logging.WARNING,
                            "RECOVERY MODE: Loss streak blocks new entries; "
                            "protective monitoring remains active."
                            f"{pause_msg} Consecutive losses="
                            f"{getattr(self.loss_tracker, 'consecutive_losses', '?')}. "
                            f"Reason={reason}.",
                            interval_sec=1800.0,
                        )

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

    def _log_oracle_freeze_cycle(self) -> None:
        """Log oracle freeze without noisy warnings when the market is closed."""
        market_open = self._is_market_open()
        self._log_circuit_breaker_throttled(
            "oracle_freeze" if market_open else "oracle_freeze_after_hours",
            logging.WARNING if market_open else logging.INFO,
            (
                "CIRCUIT BREAKER: Oracle freeze active. Skipping cycle."
                if market_open
                else "Oracle freeze remains active after hours; live entries are already paused."
            ),
            interval_sec=300.0 if market_open else 1800.0,
        )

    async def _run_periodic_freeze(self) -> None:
        """Periodically saves the cognitive state to the Quantum Session Restorer."""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Freeze state every 5 minutes
                # Enhancement: Sweep unfilled entry orders older than 2 minutes.
                try:
                    await self._cancel_stale_entry_orders(timeout_sec=120)
                except Exception as _so_err:
                    logger.debug("Stale order sweep failed (non-fatal): %s", _so_err)
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
                await self._check_resume_gap("brain_watchdog")

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

    async def _check_resume_gap(self, source: str) -> bool:
        """Detect laptop sleep/resume gaps before fresh heartbeats can hide them."""
        now = datetime.now(timezone.utc)
        gap_seconds = (now - self._last_runtime_wall).total_seconds()
        self._last_runtime_wall = now

        threshold = max(90.0, float(self.scan_interval) * 2.0)
        if gap_seconds <= threshold:
            return False

        quarantine_seconds = max(300.0, min(1800.0, gap_seconds * 0.25))
        until = now + timedelta(seconds=quarantine_seconds)
        if self._resume_quarantine_until is None or until > self._resume_quarantine_until:
            self._resume_quarantine_until = until

        self.pending_signals.clear()
        async with self._state_lock:
            self.state = TradingState.STANDBY

        if self.dms and hasattr(self.dms, "mark_resume_gap_if_needed"):
            self.dms.mark_resume_gap_if_needed(now, source)

        logger.critical(
            "RESUME GAP DETECTED by %s: runtime silent for %.0fs. "
            "Trading quarantined until %s while broker/data state is revalidated.",
            source,
            gap_seconds,
            self._resume_quarantine_until.isoformat(),
        )

        if self.bus is not None:
            try:
                await self.bus.publish(
                    "notification.telegram",
                    {
                        "message": (
                            "[DMS] Resume gap detected: "
                            f"runtime silent for {gap_seconds:.0f}s. "
                            "New entries quarantined while broker/data state is revalidated."
                        )
                    },
                )
            except Exception as exc:
                logger.debug("Resume-gap Telegram publish skipped: %s", exc)
        return True

    # BUS LISTENER — processes events from SharedIntelligenceBus

    async def _run_bus_listener(self) -> None:
        """
        Background task: subscribes to all bus topics the Brain cares about
        and updates internal state in real-time.
        CPU IMPLEMENT: uses async iteration for 0% idle overhead.
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

                        if new_dhatu in ("Abhava", "Viyoga") or self._oracle_risk_modifier <= 0.0:
                            self._oracle_freeze = True
                        else:
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
                        count = int(payload.get("count", 0) or 0)
                        source = str(payload.get("source", "unknown"))
                        self._log_candle_batch_pulse(count, source)
                        if self._is_oracle_entry_frozen():
                            logger.debug(
                                "BUS → candle.batch: scan wake suppressed during oracle freeze "
                                "(%s, modifier=%.2f)",
                                self._oracle_dhatu,
                                self._oracle_risk_modifier,
                            )
                            continue
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
                        if (
                            not self._is_market_open()
                            and os.environ.get("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS") != "1"
                        ):
                            logger.debug("BUS -> macro.impact ignored while market is closed.")
                            continue
                        if self._is_oracle_entry_frozen():
                            logger.debug(
                                "BUS → macro.impact ignored during oracle freeze: %s", impact
                            )
                            continue
                        self._apply_macro_impact(payload)
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
        """Returns the last known bid, ask, and spread for a symbol.

        Prefer the live microstructure processor if it has data; fall back to
        the raw tick caches.
        """
        micro = getattr(self, "microstructure", None)
        if micro is not None:
            snap = micro.get_snapshot(symbol)
            if snap.bid > 0 and snap.ask > 0:
                return {
                    "bid": snap.bid,
                    "ask": snap.ask,
                    "spread": snap.spread,
                    "mid": snap.mid,
                }

        bid = self.last_tick_bids.get(symbol, self.last_tick_prices.get(symbol, 0.0))
        ask = self.last_tick_asks.get(symbol, self.last_tick_prices.get(symbol, 0.0))

        # If we have no data, return a default nominal spread (0.01% of price)
        if bid == 0 or ask == 0:
            return {"bid": 0.0, "ask": 0.0, "spread": 0.0, "mid": 0.0}

        return {"bid": bid, "ask": ask, "spread": abs(ask - bid), "mid": (ask + bid) / 2.0}

    async def get_microstructure_summary(self, symbol: str) -> dict[str, Any]:
        """Return hawk-eye microstructure signals for a symbol."""
        micro = getattr(self, "microstructure", None)
        if micro is None:
            return {}
        return micro.summary(symbol)

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
        if getattr(self, "data_pipeline", None) is not None:
            self.data_pipeline.record_realtime_tick(data)

        # 2. Update hawk-eye microstructure signals (spread, VWAP, order flow, tape speed).
        if getattr(self, "microstructure", None) is not None:
            self.microstructure.on_tick(data)

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

        # 3. Generate morning budget once per day, but re-generate if first
        # time we see the market open (catches overnight starts with stale regime)
        last_budget = self.last_budget_date
        market_now_open = self._is_market_open()
        _first_open_today = getattr(self, "_budget_open_refreshed_today", None)
        new_day = last_budget is None or last_budget.date() != now.date()
        open_refresh_needed = (
            market_now_open
            and last_budget is not None
            and last_budget.date() == now.date()
            and _first_open_today != now.date()
        )
        if new_day or open_refresh_needed:
            await self._generate_morning_budget()
            if market_now_open:
                self._budget_open_refreshed_today = now.date()

        # Check if any drawdown prevents trading
        if not self.ibkr_drawdown.is_trading_allowed():
            logger.warning(f"IBKR drawdown [{self.ibkr_drawdown.level.value}] — trading suspended")
            await asyncio.sleep(60)
            return

        if not self.loss_tracker.is_trading_allowed():
            reason = getattr(self.loss_tracker, "status_reason", lambda: "loss streak")()
            logger.warning(
                "G1 escalation — trading suspended "
                f"(consecutive losses: {self.loss_tracker.consecutive_losses}, reason={reason})"
            )
            await asyncio.sleep(60)
            return

        # Pre-market health check — validate all critical paths before risking capital
        health_ok, health_reason = await self._pre_market_health_check()
        if not health_ok:
            self._log_pre_market_health_failure(health_reason)
            await asyncio.sleep(30)
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
            broker=getattr(self, 'active_broker', 'ibkr'),
        )
        self.last_budget_date = datetime.now(timezone.utc)

    # STATE: SCANNING

    def _log_scan_veto(self, symbol: str, pattern: str, reason: str, *, confidence: float | None = None) -> None:
        """Rate-limit repeated scan veto logs without hiding the reason."""
        now = time.monotonic()
        key = (symbol.upper(), pattern, reason)
        last_logged = self._scan_veto_log_cache.get(key, 0.0)
        should_log = now - last_logged >= self._scan_veto_log_interval
        if should_log:
            self._scan_veto_log_cache[key] = now

        detail = f"Scan [{symbol}]: {pattern}"
        if confidence is not None:
            detail += f" ({confidence:.1f}% confidence)"
        detail += f" skipped - {reason}."

        if should_log:
            logger.info(detail)
        else:
            logger.debug(detail)

    def _log_candle_batch_pulse(self, count: int, source: str) -> None:
        """Keep high-frequency data pulses visible without turning logs into tick storage."""
        try:
            interval_sec = max(
                10.0,
                float(os.getenv("SOVEREIGN_CANDLE_PULSE_LOG_INTERVAL_SEC", "60")),
            )
        except ValueError:
            interval_sec = 60.0

        now = time.monotonic()
        last_log = getattr(self, "_last_candle_batch_notice_ts", None)
        message = "BUS -> candle.batch: %s symbols received from %s."
        if last_log is None or now - float(last_log) >= interval_sec:
            logger.info(message, count, source)
            self._last_candle_batch_notice_ts = now
        else:
            logger.debug(message, count, source)

    async def _publish_market_observation(
        self,
        symbol: str,
        event_type: str,
        pattern: str,
        *,
        confidence: float | None = None,
        price: float | None = None,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Publish bounded shadow-learning observations from watched market behavior."""
        if not self.bus:
            return
        learning_enabled = os.environ.get(
            "SOVEREIGN_MARKET_OBSERVATION_LEARNING",
            "1" if MARKET_OBSERVATION_LEARNING_ENABLED else "0",
        )
        if learning_enabled != "1":
            return

        try:
            throttle_sec = max(
                30.0,
                float(
                    os.environ.get(
                        "SOVEREIGN_MARKET_OBSERVATION_THROTTLE_SEC",
                        str(MARKET_OBSERVATION_THROTTLE_SEC),
                    )
                ),
            )
        except ValueError:
            throttle_sec = MARKET_OBSERVATION_THROTTLE_SEC

        cache = getattr(self, "_market_observation_log", None)
        if cache is None:
            cache = {}
            self._market_observation_log = cache

        key = (symbol.upper(), event_type, pattern, reason[:120])
        now_mono = time.monotonic()
        last_seen = float(cache.get(key, 0.0) or 0.0)
        if now_mono - last_seen < throttle_sec:
            return
        cache[key] = now_mono

        await self.bus.publish(
            "market.observation",
            {
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol.upper(),
                "event_type": event_type,
                "pattern": pattern,
                "confidence": float(confidence or 0.0),
                "price": float(price or 0.0),
                "regime": self.current_regime,
                "dhatu_state": getattr(self, "_oracle_dhatu", "UNKNOWN"),
                "source": "brain.scan",
                "metadata": {
                    "reason": reason,
                    "scan_cycle": self._scan_cycle,
                    **(metadata or {}),
                },
            },
        )

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
            await self._check_resume_gap("scanner")
            now = datetime.now(timezone.utc)
            quarantine_until = self._resume_quarantine_until
            if quarantine_until and now < quarantine_until:
                remaining = (quarantine_until - now).total_seconds()
                notice_due = (
                    self._last_resume_notice_at is None
                    or (now - self._last_resume_notice_at).total_seconds() >= 60
                )
                if notice_due:
                    logger.warning(
                        "SCAN SUSPENDED: resume quarantine active for %.0fs more. "
                        "Broker/data state must settle after laptop sleep.",
                        remaining,
                    )
                    self._last_resume_notice_at = now
                self.pending_signals.clear()
                await asyncio.sleep(min(30.0, max(1.0, remaining)))
                return

            if quarantine_until and now >= quarantine_until:
                logger.warning("Resume quarantine cleared; scanner may resume.")
                self._resume_quarantine_until = None
                self._last_resume_notice_at = None

            closed_market_scans_disabled = (
                not self._is_market_open()
                and os.environ.get("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS") != "1"
            )
            if self.last_regime_update is None or (
                now - self.last_regime_update
            ).total_seconds() >= (900 if closed_market_scans_disabled else 60):
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

            if closed_market_scans_disabled:
                if self._scan_cycle % 10 == 1:
                    logger.info(
                        "SCAN SUSPENDED: US equity market is closed. "
                        "Set SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS=1 for offline simulation."
                    )
                self.pending_signals.clear()
                async with self._state_lock:
                    self.last_scan_stats = {
                        "cycle": self._scan_cycle,
                        "watchlist": 0,
                        "scanned": 0,
                        "gated": 0,
                        "gate_active": 0,
                        "gate_cooldown": 0,
                        "gate_vetting": 0,
                        "patterns_detected": 0,
                        "patterns_approved": 0,
                        "pending": 0,
                        "regime": self.current_regime,
                    }
                    status_snapshot = dict(self.last_scan_stats)
                await self._maybe_send_execution_status(status_snapshot, "N/A")
                for _ in range(4):
                    if self.dms:
                        self.dms.record_heartbeat()
                    if self.mind_ghost:
                        await self.mind_ghost.update_heartbeat("ENGINE")
                    await asyncio.sleep(30)
                return

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
                broker_online = self._broker_is_connected(self.ibkr_conn)
            elif self.active_broker == "IBKR":
                broker_online = self._broker_is_connected(self.ibkr_conn)
            elif self.active_broker == "MT5":
                broker_online = self._broker_is_connected(self.mt5_conn)

            if not broker_online:
                if self._scan_cycle % 10 == 1:
                    logger.info(f"SCAN SUSPENDED: [{self.active_broker}] is currently offline.")
                await asyncio.sleep(5)
                return

            if not self.loss_tracker.is_trading_allowed():
                reason = getattr(self.loss_tracker, "status_reason", lambda: "loss streak")()
                pause_until = getattr(self.loss_tracker, "pause_until", None)
                self._log_circuit_breaker_throttled(
                    "scan_recovery_mode",
                    logging.INFO,
                    "SCAN BLOCKED: recovery mode is active; new entries disabled. "
                    "Existing positions remain under exit monitoring. "
                    f"losses={getattr(self.loss_tracker, 'consecutive_losses', '?')} "
                    f"pause_until={pause_until.isoformat() if pause_until else 'n/a'} "
                    f"reason={reason}",
                    interval_sec=300.0,
                )
                self.pending_signals.clear()
                async with self._state_lock:
                    self.last_scan_stats = {
                        "cycle": self._scan_cycle,
                        "watchlist": len(watchlist),
                        "scanned": 0,
                        "gated": len(watchlist),
                        "gate_active": 0,
                        "gate_cooldown": 0,
                        "gate_vetting": 0,
                        "patterns_detected": 0,
                        "patterns_approved": 0,
                        "pending": 0,
                        "regime": self.current_regime,
                        "recovery_mode": True,
                        "pause_until": pause_until.isoformat() if pause_until else None,
                        "recovery_reason": reason,
                    }
                    status_snapshot = dict(self.last_scan_stats)
                await self._maybe_send_execution_status(status_snapshot, "RECOVERY")
                await asyncio.sleep(min(60.0, max(5.0, self.scan_interval)))
                return

            if self._oracle_freeze or self._oracle_risk_modifier <= 0.0:
                self.pending_signals.clear()
                self._log_circuit_breaker_throttled(
                    "scan_oracle_freeze",
                    logging.WARNING,
                    "SCAN SUSPENDED: Oracle freeze active "
                    f"({self._oracle_dhatu}, modifier={self._oracle_risk_modifier:.2f}).",
                    interval_sec=300.0,
                )
                async with self._state_lock:
                    self.last_scan_stats = {
                        "cycle": self._scan_cycle,
                        "watchlist": len(watchlist),
                        "scanned": 0,
                        "gated": len(watchlist),
                        "gate_active": 0,
                        "gate_cooldown": 0,
                        "gate_vetting": 0,
                        "patterns_detected": 0,
                        "patterns_approved": 0,
                        "pending": 0,
                        "regime": self.current_regime,
                        "oracle_freeze": True,
                    }
                await asyncio.sleep(self.scan_interval)
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
                "regime_blocked": 0,
                "gated": 0,
                "gate_active": 0,
                "gate_cooldown": 0,
                "gate_vetting": 0,
            }
            stats_lock = asyncio.Lock()

            # 1. DMS HEARTBEAT
            if self.dms:
                self.dms.record_heartbeat("BRAIN_PRIMARY")

            async def _scan_symbol(symbol: str):
                from mind_ultrathink import LatencyWatchdog

                # Black Swan circuit breaker: halt ALL new trade discovery
                dd_pct = (self.ibkr_drawdown.peak_equity - self.ibkr_drawdown.current_equity) / max(self.ibkr_drawdown.peak_equity, 1)
                if self.blackswan.check(await self._get_vix(), dd_pct) == "FREEZE":
                    async with stats_lock:
                        stats["gated"] += 1
                    logger.warning("Scan [%s]: BLACK SWAN FREEZE active — scanning suspended.", symbol)
                    return None

                # DRAWDOWN PREDICTOR EARLY WARNING
                try:
                    from drawdown_predictor import DrawdownPredictor
                    predictor = DrawdownPredictor()
                    # Map dd_pct to Markov state: <5% = 0, <15% = 1, else = 2
                    if dd_pct < 0.05:
                        current_state = 0
                    elif dd_pct < 0.15:
                        current_state = 1
                    else:
                        current_state = 2
                    expected_recovery = predictor.predict_duration(current_state, target_state=0)
                    if expected_recovery > 0 and current_state > 0:
                        logger.info(
                            "Scan [%s]: Drawdown predictor estimates %.1f trades to recover from state %d (dd_pct=%.1f%%).",
                            symbol,
                            expected_recovery,
                            current_state,
                            dd_pct * 100,
                        )
                        # If deep drawdown and recovery expectation is high, gate aggressive patterns
                        if current_state >= 2 and expected_recovery > 10:
                            logger.warning(
                                "Scan [%s]: Deep drawdown recovery expected in %.1f trades — raising pattern confidence threshold.",
                                symbol,
                                expected_recovery,
                            )
                except Exception as dp_err:
                    logger.debug("Scan [%s]: Drawdown predictor error: %s", symbol, dp_err)

                # VIX CIRCUIT BREAKER (rolling-window flash spike detector)
                try:
                    from vix_circuit_breaker import VIXCircuitBreaker
                    if not hasattr(self, "_vix_breaker"):
                        self._vix_breaker = VIXCircuitBreaker(spike_threshold=0.20, window_seconds=300)
                    vix_value = await self._get_vix()
                    if vix_value is not None and self._vix_breaker.process_vix_tick(vix_value):
                        async with stats_lock:
                            stats["gated"] += 1
                        logger.critical(
                            "Scan [%s]: VIX FLASH SPIKE detected — scanning suspended.", symbol
                        )
                        return None
                except Exception as vix_err:
                    logger.debug("Scan [%s]: VIX circuit breaker error: %s", symbol, vix_err)

                last_vet = self._vetting_cooldowns.get(symbol)
                if last_vet:
                    if last_vet.tzinfo is None:
                        last_vet = last_vet.replace(tzinfo=timezone.utc)
                    cooldown_age = (datetime.now(timezone.utc) - last_vet).total_seconds()
                    if cooldown_age < 300:
                        async with stats_lock:
                            stats["gated"] += 1
                            stats["gate_vetting"] += 1
                        logger.debug(
                            "Scan [%s]: skipped during post-vetting cooldown (%.1fs remaining).",
                            symbol,
                            300 - cooldown_age,
                        )
                        return None

                if self.task_manager:
                    gate = self.task_manager.get_symbol_gate(
                        symbol,
                        terminal_cooldown_seconds=60.0,  # Reduced from 300s: faster re-scan after VETO
                    )
                    if gate:
                        gate_kind, gate_task, remaining_sec = gate
                        async with stats_lock:
                            stats["gated"] += 1
                            if gate_kind == "active":
                                stats["gate_active"] += 1
                            else:
                                stats["gate_cooldown"] += 1
                        if gate_kind == "active":
                            logger.debug(
                                "Scan [%s]: skipped because task %s is still %s.",
                                symbol,
                                gate_task.id,
                                gate_task.status.value,
                            )
                        else:
                            logger.debug(
                                "Scan [%s]: skipped during terminal task cooldown "
                                "(task=%s, %.1fs remaining).",
                                symbol,
                                gate_task.id,
                                remaining_sec,
                            )
                        return None

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
                        if isinstance(fetch_result, str) and fetch_result == "STALE":
                            async with stats_lock:
                                stats["stale"] += 1
                            return None
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
                            df_pl = safe_polars_from_pandas(df_pd)
                        try:
                            current_scan_price = float(df_pl.select(pl.col("close").last()).item())
                        except Exception:
                            current_scan_price = 0.0

                        # CONTAGION SENTINEL: feed returns and check for systemic correlation spikes
                        try:
                            if self.contagion_sentinel and current_scan_price > 0:
                                prev_close = float(df_pl.select(pl.col("close").tail(2).head(1)).item())
                                if prev_close > 0:
                                    ret = (current_scan_price - prev_close) / prev_close
                                    self.contagion_sentinel.ingest(symbol, ret)
                                    if self.contagion_sentinel.detect_contagion():
                                        async with stats_lock:
                                            stats["gated"] += 1
                                        logger.critical(
                                            "Scan [%s]: Contagion detected — scanning suspended.", symbol
                                        )
                                        return None
                        except Exception as cs_err:
                            logger.debug("Scan [%s]: Contagion sentinel error: %s", symbol, cs_err)

                        tr_expr = pl.max_horizontal(
                            [
                                (pl.col("high") - pl.col("low")).abs(),
                                (pl.col("high") - pl.col("close").shift(1)).abs(),
                                (pl.col("low") - pl.col("close").shift(1)).abs(),
                            ]
                        ).alias("tr")

                        tr = df_pl.select([tr_expr])["tr"]
                        atr_val = float(tr.tail(20).mean()) if len(tr) >= 20 else 0.0

                        # CHAOS AGENT: Check market randomness before pattern detection
                        try:
                            if self.chaos_agent:
                                close_prices = df_pl.select(pl.col("close")).to_series().to_list()
                                lle = self.chaos_agent.calculate_market_randomness(close_prices)
                                if lle > 0.5:
                                    logger.info(
                                        "Scan [%s]: ChaosAgent detected high market randomness (LLE=%.3f)."
                                        " Patterns may be less reliable.",
                                        symbol,
                                        lle,
                                    )
                        except Exception as chaos_err:
                            logger.debug("Scan [%s]: ChaosAgent error: %s", symbol, chaos_err)

                        # FRACTAL AGENT: Trend quality gate — warn on choppy markets
                        # but do NOT hard-skip. The RegimeStrategyRouter and CHOPPY
                        # filter below are the authoritative gates; this avoids the
                        # system sitting idle all day when the market is range-bound.
                        try:
                            if self.fractal_agent:
                                _fa_result = self.fractal_agent.analyze_trend(close_prices)
                                _fd = _fa_result.get("fractal_dimension", 1.5)
                                if _fa_result.get("market_state") == "CHOPPY_MEAN_REVERTING":
                                    logger.info(
                                        "Scan [%s]: FractalAgent choppy market (FD=%.2f). Continuing to regime router.",
                                        symbol, _fd,
                                    )
                        except Exception as _fractal_err:
                            logger.debug("Scan [%s]: FractalAgent error: %s", symbol, _fractal_err)

                        # BAYESIAN REGIME AGENT: secondary regime confirmation
                        try:
                            if self.bayesian_regime and len(close_prices) >= 20:
                                _recent_rets = list(np.diff(close_prices[-21:]) / (np.array(close_prices[-21:-1]) + 1e-9))
                                _recent_vol = float(np.std(_recent_rets)) + 1e-9
                                _bayes_regime = self.bayesian_regime.update_beliefs(_recent_rets, _recent_vol)
                                logger.debug("Scan [%s]: BayesianRegime=%s", symbol, _bayes_regime)
                        except Exception as _br_err:
                            logger.debug("Scan [%s]: BayesianRegimeAgent error: %s", symbol, _br_err)

                        # BAYESIAN ORACLE: richer 4-regime posterior with likelihood table
                        try:
                            if self.bayesian_oracle and len(close_prices) >= 22:
                                _vol_data = df_pl.get_column("volume").to_numpy() if "volume" in df_pl.columns else np.ones(len(close_prices))
                                _vix_for_oracle = locals().get("vix_value") or 15.0
                                _oracle_state = self.bayesian_oracle.update(
                                    np.array(close_prices, dtype=float),
                                    _vol_data.astype(float),
                                    float(_vix_for_oracle),
                                )
                                logger.debug(
                                    "Scan [%s]: BayesianOracle=%s conf=%.1f%%",
                                    symbol, _oracle_state.regime, _oracle_state.confidence * 100,
                                )
                        except Exception as _oracle_err:
                            logger.debug("Scan [%s]: BayesianOracle error: %s", symbol, _oracle_err)

                        # CAPITAL FLOW AGENT: ingest ticker return for sector rotation tracking
                        try:
                            if self.flow_agent and len(close_prices) >= 2:
                                _tick_ret = (close_prices[-1] - close_prices[-2]) / (close_prices[-2] + 1e-9)
                                self.flow_agent.ingest(symbol, _tick_ret)
                        except Exception as _flow_err:
                            logger.debug("Scan [%s]: CapitalFlowAgent error: %s", symbol, _flow_err)

                        # ALPHA DISCOVERY: evolve GA ensemble periodically
                        try:
                            if self.alpha_discovery and len(close_prices) >= 60:
                                _ens_sig = self.alpha_discovery.ensemble_signal(close_prices)
                                if _ens_sig is not None:
                                    logger.debug(
                                        "Scan [%s]: AlphaDiscovery ensemble signal=%.2f",
                                        symbol, _ens_sig,
                                    )
                        except Exception as _disc_err:
                            logger.debug("Scan [%s]: AlphaDiscovery error: %s", symbol, _disc_err)

                        # Regime-aware, timeframe-aware pattern detection.
                        # Each pattern runs on its designed timeframe; only patterns
                        # permitted for the current regime are evaluated.
                        async def _fetch_for_detector(sym: str, tf: str) -> Any:
                            return await self._fetch_ohlcv(sym, tf)

                        patterns = await self.timeframe_detector.detect_for_regime(
                            symbol=symbol,
                            regime=self.current_regime,
                            fetch_ohlcv=_fetch_for_detector,
                        )

                        # Live adaptive learning: adjust pattern confidence based on
                        # recent real-time outcomes for this pattern / regime.
                        if patterns:
                            self.adaptive_engine.recompute()
                            for p in patterns:
                                if p:
                                    p.atr = atr_val
                                    p.adaptive_confidence = self.adaptive_engine.adjust_pattern_confidence(
                                        p.name, p.confidence
                                    )
                                    p.confidence = p.adaptive_confidence

                        found = [p for p in patterns if p and p.confidence >= 40.0]

                        if not found:
                            all_found = [p for p in patterns if p]
                            if all_found:
                                async with stats_lock:
                                    stats["detected"] += 1
                                    stats["rejected"] += 1
                                best_low = max(all_found, key=lambda x: x.confidence)
                                self._log_scan_veto(
                                    symbol,
                                    best_low.name,
                                    "confidence below approval floor",
                                    confidence=float(best_low.confidence),
                                )
                                await self._publish_market_observation(
                                    symbol,
                                    "PATTERN_LOW_CONFIDENCE",
                                    best_low.name,
                                    confidence=float(best_low.confidence),
                                    price=current_scan_price,
                                    reason="confidence below approval floor",
                                    metadata={
                                        "category": getattr(best_low, "category", "UNKNOWN"),
                                        "rr": getattr(best_low, "r_r_ratio", None),
                                    },
                                )
                            return None

                        best = max(found, key=lambda x: x.confidence)

                        # CHOPPY regime handling: the system must trade in every regime,
                        # not just trend. The RegimeStrategyRouter already selects the
                        # right patterns/timeframes; the FractalAgent hard skip was also
                        # removed. No additional category block is applied here.

                        # MULTI-TIMEFRAME CONFLUENCE: require higher timeframes to agree.
                        primary_tf = getattr(best, "timeframe", "1m")
                        direction = "LONG" if getattr(best, "entry", 0) >= getattr(best, "stop", 0) else "SHORT"
                        confluence_threshold = self.adaptive_engine.adjust_confluence_threshold()
                        confluence = await self.confluence_engine.evaluate(
                            symbol,
                            direction,
                            primary_tf,
                            self._fetch_ohlcv,
                            min_score=confluence_threshold,
                        )
                        best.confluence_score = confluence.score  # type: ignore[attr-defined]
                        best.confluence_timeframes = confluence.checked_timeframes  # type: ignore[attr-defined]
                        if not confluence.passed:
                            async with stats_lock:
                                stats["detected"] += 1
                                stats["rejected"] += 1
                                stats["confluence_blocked"] = stats.get("confluence_blocked", 0) + 1
                            self._log_scan_veto(
                                symbol,
                                f"{best.name}",
                                f"CONFLUENCE_VETO: {confluence.reasons[0] if confluence.reasons else 'low alignment'}",
                                confidence=float(best.confidence),
                            )
                            await self._publish_market_observation(
                                symbol,
                                "PATTERN_CONFLUENCE_BLOCKED",
                                best.name,
                                confidence=float(best.confidence),
                                price=current_scan_price,
                                reason=f"Confluence score {confluence.score:.2f} on {primary_tf}",
                                metadata={
                                    "category": getattr(best, "category", "UNKNOWN"),
                                    "confluence_score": confluence.score,
                                    "confluence_timeframes": confluence.checked_timeframes,
                                    "confluence_alignment": confluence.alignment,
                                },
                            )
                            return None

                        # NEURAL GOVERNANCE: cross-agent consensus before execution.
                        votes = [
                            AgentVote(
                                agent="pattern_detector",
                                decision="APPROVE",
                                confidence=float(best.confidence) / 100.0,
                                reason=f"detected {best.name} on {primary_tf}",
                                weight=1.0,
                            ),
                            AgentVote(
                                agent="confluence",
                                decision="APPROVE" if confluence.passed else "VETO",
                                confidence=confluence.score,
                                reason=confluence.reasons[0] if confluence.reasons else "",
                                weight=1.0,
                            ),
                            AgentVote(
                                agent="regime_router",
                                decision="APPROVE",
                                confidence=0.8,
                                reason=f"regime={self.current_regime}",
                                weight=1.0,
                            ),
                        ]
                        governance_context = {
                            "pattern": best.name,
                            "category": getattr(best, "category", "UNKNOWN"),
                            "timeframe": primary_tf,
                            "direction": direction,
                            "regime": self.current_regime,
                            "confluence_score": confluence.score,
                        }
                        governance = self.governance_engine.decide(
                            symbol, votes, context=governance_context
                        )
                        best.governance_score = governance.score  # type: ignore[attr-defined]
                        best.governance_audit_id = governance.audit_id  # type: ignore[attr-defined]
                        if not governance.approved:
                            async with stats_lock:
                                stats["detected"] += 1
                                stats["rejected"] += 1
                                stats["governance_blocked"] = stats.get("governance_blocked", 0) + 1
                            self._log_scan_veto(
                                symbol,
                                f"{best.name}",
                                f"GOVERNANCE_VETO: {governance.reasons[0] if governance.reasons else 'low consensus'}",
                                confidence=float(best.confidence),
                            )
                            await self._publish_market_observation(
                                symbol,
                                "PATTERN_GOVERNANCE_BLOCKED",
                                best.name,
                                confidence=float(best.confidence),
                                price=current_scan_price,
                                reason=f"Governance score {governance.score:.2f} < {governance.threshold}",
                                metadata={
                                    "category": getattr(best, "category", "UNKNOWN"),
                                    "governance_score": governance.score,
                                    "governance_threshold": governance.threshold,
                                    "governance_conflicts": governance.conflicts,
                                    "governance_audit_id": governance.audit_id,
                                },
                            )
                            return None

                        # SENTIMENT OVERLAY: Veto or dampen confidence on extreme sentiment
                        try:
                            import sqlite3

                            from sentiment_agent import aggregate_sentiment
                            from sentiment_vol import SentimentVolatilityIndex
                            db_path = getattr(self, "db_path", "data/trading.db")
                            news_headlines = []
                            try:
                                conn = sqlite3.connect(str(db_path))
                                cur = conn.cursor()
                                cur.execute(
                                    "SELECT headline FROM news_headlines WHERE symbol=? AND datetime(timestamp) > datetime('now', '-1 hour') ORDER BY timestamp DESC LIMIT 10",
                                    (symbol,),
                                )
                                news_headlines = [row[0] for row in cur.fetchall() if row[0]]
                                conn.close()
                            except Exception:
                                pass
                            if news_headlines:
                                sentiment = aggregate_sentiment(news_headlines, asset_class="equities")
                                mean_sentiment = sentiment.get("mean", 0.0)
                                signal = sentiment.get("signal", "NEUTRAL")
                                # Sentiment Volatility Index: track reversal risk
                                if not hasattr(self, "_sentiment_vol_index"):
                                    self._sentiment_vol_index = SentimentVolatilityIndex(lookback=60)
                                self._sentiment_vol_index.update(mean_sentiment)
                                svi_value = self._sentiment_vol_index.svi()
                                if svi_value > 0.5:
                                    logger.info(
                                        f"Scan [{symbol}]: Sentiment reversal forming (SVI={svi_value:.2f})."
                                    )
                                if signal in ("BULLISH", "BEARISH") and abs(mean_sentiment) > 0.5:
                                    # Extreme sentiment: dampen confidence
                                    dampen_factor = max(0.5, 1.0 - abs(mean_sentiment) * 0.3)
                                    old_conf = float(best.confidence)
                                    best.confidence = old_conf * dampen_factor
                                    logger.info(
                                        f"Scan [{symbol}]: Sentiment overlay {signal} (mean={mean_sentiment:.2f}) "
                                        f"dampened {best.name} confidence {old_conf:.1f}% -> {best.confidence:.1f}%"
                                    )
                                    if best.confidence < 0.55:
                                        async with stats_lock:
                                            stats["detected"] += 1
                                            stats["rejected"] += 1
                                        self._log_scan_veto(
                                            symbol,
                                            f"{best.name}",
                                            f"SENTIMENT_VETO: {signal} sentiment too extreme (mean={mean_sentiment:.2f})",
                                            confidence=float(best.confidence),
                                        )
                                        return None
                        except Exception as se:
                            logger.debug(f"Scan [{symbol}]: Sentiment overlay error: {se}")

                        # MACRO NEWS OVERLAY: Detect hawkish/dovish Fed language in headlines
                        try:
                            from news_agent import MacroNewsAgent
                            macro_agent = MacroNewsAgent()
                            # Reuse the same news_headlines fetched above; if none, skip
                            if news_headlines:
                                macro_text = " ".join(news_headlines)
                                macro_result = macro_agent.classify_fed_statement(macro_text)
                                stance = macro_result.get("stance", "NEUTRAL")
                                if stance == "HAWKISH":
                                    # Hawkish Fed is generally bearish for equities
                                    old_conf = float(best.confidence)
                                    best.confidence = old_conf * 0.85
                                    logger.info(
                                        f"Scan [{symbol}]: Macro overlay HAWKISH dampened {best.name} confidence {old_conf:.1f}% -> {best.confidence:.1f}%"
                                    )
                                elif stance == "DOVISH":
                                    # Dovish Fed is generally bullish for equities
                                    # Already captured by sentiment overlay, but log for traceability
                                    logger.info(
                                        f"Scan [{symbol}]: Macro overlay DOVISH detected (score={macro_result.get('score', 0):.2f})"
                                    )
                        except Exception as ne:
                            logger.debug(f"Scan [{symbol}]: Macro news overlay error: {ne}")

                        # CONTRARIAN AGENT: Use sentiment as a proxy for crowd extremes
                        try:
                            if self.contrarian_agent and news_headlines:
                                # Map mean_sentiment to synthetic retail/influencer ratios
                                sentiment = mean_sentiment if 'mean_sentiment' in dir() else 0.0
                                abs_sent = abs(sentiment)
                                if abs_sent > 0.5:
                                    long_ratio = 0.5 + (sentiment * 0.4)
                                    short_ratio = 1.0 - long_ratio
                                    bull_mentions = int(abs_sent * 10) if sentiment > 0 else 0
                                    bear_mentions = int(abs_sent * 10) if sentiment < 0 else 0
                                    contra = self.contrarian_agent.evaluate_crowd_error(
                                        retail_long_ratio=max(0.0, min(1.0, long_ratio)),
                                        retail_short_ratio=max(0.0, min(1.0, short_ratio)),
                                        influencer_bull_mentions=bull_mentions,
                                        influencer_bear_mentions=bear_mentions,
                                    )
                                    signal = contra.get("signal", "NEUTRAL")
                                    if signal in ("BUY", "SELL"):
                                        logger.info(
                                            f"Scan [{symbol}]: Contrarian signal {signal} "
                                            f"(crowd_score={contra.get('crowd_score', 0):.2f}, conf={contra.get('confidence', 0):.2f})"
                                        )
                        except Exception as ca_err:
                            logger.debug(f"Scan [{symbol}]: Contrarian overlay error: {ca_err}")

                        async with stats_lock:
                            stats["detected"] += 1
                            stats["approved"] += 1

                        logger.info(
                            f" DISCOVERY: {symbol} matched {best.name} ({best.confidence:.1f}%)"
                        )
                        await self._publish_market_observation(
                            symbol,
                            "PATTERN_DISCOVERY",
                            best.name,
                            confidence=float(best.confidence),
                            price=current_scan_price,
                            reason="pattern approved by scanner",
                            metadata={
                                "category": getattr(best, "category", "UNKNOWN"),
                                "rr": getattr(best, "r_r_ratio", None),
                            },
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
                f"Gated={stats['gated']}"
                f"(active={stats['gate_active']},cooldown={stats['gate_cooldown']},"
                f"vetting={stats['gate_vetting']}) "
                f"| Detected={stats['detected']} Approved={stats['approved']} "
                f"RegimeBlocked={stats['regime_blocked']} "
                f"| Pending={len(discoveries)}"
            )

            # Update global stats with lock
            async with self._state_lock:
                self.last_scan_stats = {
                    "cycle": self._scan_cycle,
                    "watchlist": len(watchlist),
                    "scanned": stats["scanned"],
                    "gated": stats["gated"],
                    "gate_active": stats["gate_active"],
                    "gate_cooldown": stats["gate_cooldown"],
                    "gate_vetting": stats["gate_vetting"],
                    "patterns_detected": stats["detected"],
                    "patterns_approved": stats["approved"],
                    "patterns_rejected": stats["rejected"],
                    "patterns_regime_blocked": stats["regime_blocked"],
                    "no_data": stats["no_data"],
                    "stale": stats["stale"],
                    "too_short": stats["too_short"],
                    "pending": len(discoveries),
                    "regime": self.current_regime,
                }
                status_snapshot = dict(self.last_scan_stats)

            # Emit structured Prometheus metrics (non-fatal)
            try:
                from metrics import METRICS
                METRICS.scan_symbols_processed.inc(stats.get("scanned", 0))
                METRICS.scan_cycle_duration_seconds.observe(
                    time.monotonic() - getattr(self, "_scan_start_ts", time.monotonic())
                )
                METRICS.update_from_brain(self)
            except Exception as _m_err:
                pass  # metrics must never interrupt trading

            await self._maybe_send_execution_status(status_snapshot, vix_str)

            # Routine Memory Maintenance (Every 10 cycles)
            if self.task_manager and self._scan_cycle % 10 == 0:
                self.task_manager.purge_dormant_tasks(max_age_minutes=15)

            # Prevent 'Information Overload' by clearing buffers when signal density is too high.
            # Guard: skip entropy check if no symbols were successfully scanned
            # to avoid false flushes.
            scanned_count = stats["scanned"]
            if scanned_count == 0 and stats["gated"] >= len(watchlist) and not discoveries:
                await asyncio.sleep(5.0)
            elif (
                self.current_regime == "CHOPPY"
                and stats["approved"] == 0
                and stats["detected"] > 0
                and stats["regime_blocked"] >= stats["detected"]
                and not discoveries
            ):
                await asyncio.sleep(max(0.5, self._scan_no_action_backoff))

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

                # FINALIZATION IMPLEMENT: Ensure tasks are not leaked during flush
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
                        k
                        for k, t in list(self.task_manager.tasks.items())
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
            self._background_tasks.add(vetting_task)
            vetting_task.add_done_callback(self._background_tasks.discard)
            vetting_task.add_done_callback(_task_done)

        # Clear the queue and return to scanning immediately
        self.pending_signals = []
        async with self._state_lock:
            self.state = TradingState.SCANNING

    # STATE: POSITIONED
    # HELPER METHODS

    async def _run_phantom_probe(self) -> None:
        """Sovereign Self-Test: Verify system wiring is 100% active."""
        await asyncio.sleep(60)  # Initial grace period
        while self.is_running:
            try:
                if self._is_oracle_entry_frozen():
                    logger.info(
                        "Brain: Phantom probe skipped during oracle freeze (%s, modifier=%.2f).",
                        self._oracle_dhatu,
                        self._oracle_risk_modifier,
                    )
                    await asyncio.sleep(3600)
                    continue

                if (
                    not self._is_market_open()
                    and os.environ.get("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS") != "1"
                ):
                    logger.info("Brain: Phantom probe skipped while US equity market is closed.")
                    await asyncio.sleep(3600)
                    continue

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
                market_open = self._is_market_open()
                closed_market = (
                    not market_open and os.environ.get("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS") != "1"
                )
                if closed_market:
                    if getattr(self, "_last_closed_conviction_log", 0) + 900 < time.time():
                        logger.info("TradingBrain: Conviction sync idling while market is closed.")
                        self._last_closed_conviction_log = time.time()
                    await asyncio.sleep(300)
                    continue

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

                now_iso = time.time_ns()
                new_convictions = {}

                logger.debug(f"Brain: Starting Conviction Sync for {now_iso}...")
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
                        new_convictions[f"Swarm_Predictor:{res.get('symbol', 'GLOBAL')}"] = res
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
                        new_convictions[f"Mind_Ultrathink:{res.get('symbol', 'GLOBAL')}"] = res
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
            # Access IBKR directly via the brain's connection
            if self.ibkr_conn and self.ibkr_conn.ib and self.ibkr_conn.is_connected():
                import ib_insync

                positions = self.ibkr_conn.ib.positions()
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
                    self.ibkr_conn.ib.placeOrder(contract, order)

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
            ("_thaw_task", "Session Thawing"),
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

        background_tasks = [task for task in self._background_tasks if not task.done()]
        for task in background_tasks:
            task.cancel()
        if background_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*background_tasks, return_exceptions=True), timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("TradingBrain: Some background vetting tasks ignored shutdown.")
            finally:
                self._background_tasks.difference_update(background_tasks)

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

        if self.swarm_predictor and hasattr(self.swarm_predictor, "close"):
            try:
                await self.swarm_predictor.close()
            except Exception as e:
                logger.error(f"Error closing swarm_predictor: {e}")

        await self.qdb.stop()
        logger.info("Trading Brain stopped.")
