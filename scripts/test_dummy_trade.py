"""End-to-end dummy trade test.

Verifies that a synthetic pattern can flow through the now-relaxed
scan-phase and coordinator-level gates and result in a trade attempt.
Uses IBKR paper mode with a mock broker backend so no real capital is at risk.

Usage:
    SOVEREIGN_SKIP_PID_CHECK=1 python scripts/test_dummy_trade.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")

sys.path.insert(0, "src")

# Env overrides for a safe, offline-ish test run
os.environ.setdefault("TRADING_MODE", "ibkr_paper")
os.environ.setdefault("SOVEREIGN_SKIP_PID_CHECK", "1")
os.environ.setdefault("SOVEREIGN_ALLOW_CLOSED_MARKET_SCANS", "1")
os.environ.setdefault("SOVEREIGN_BACKTEST_GATE", "0")

import polars as pl

from adaptive_learning import LiveAdaptiveEngine
from agent_a import PatternResult
from confluence_engine import ConfluenceEngine
from coordinator import TradingCoordinator
from neural_governance import NeuralGovernanceEngine
from strategy_router import RegimeStrategyRouter


def make_pattern() -> PatternResult:
    """Create a real PatternResult that satisfies all coordinator checks."""
    return PatternResult(
        name="Descending Triangle",
        category="SWING",
        confidence=75.0,
        entry=100.0,
        stop=99.0,
        target=103.0,
        r_r_ratio=3.0,
        confirmed=True,
        lambda_val=10,
        atr=0.5,
    )


class DummyBridge:
    """Minimal bridge stub for TradingCoordinator."""


class DummySkillTree:
    """Minimal skill tree stub."""

    def is_unlocked(self, skill: str) -> bool:
        return True


class DummyTradeInterrogator:
    """Always-pass trade interrogator stub."""

    def interrogate(self, symbol, pattern, context, **kwargs):
        class Result:
            passed = True
            reasons = []
            score = 1.0
        return Result()


class DummySizer:
    """Minimal position sizer stub."""

    def calculate(self, **kwargs):
        stop = kwargs.get("stop_price", 99.0)
        target = kwargs.get("target_price", 103.0)
        return {
            "step8_shares": 10,
            "shares": 10,
            "dollar_risk": 10.0,
            "risk_pct": 0.0002,
            "position_value": 1000.0,
            "total_multiplier": 1.0,
            "stop_price": stop,
            "target_price": target,
        }


class DummyRegimeClassifier:
    """Minimal regime classifier stub."""

    def get_risk_modifier(self, regime: str):
        return 1.0


class DummyDrawdownModifier:
    """Minimal drawdown modifier stub."""

    class level:
        value = "NORMAL"

    def get_size_modifier(self):
        return 1.0


class DummyLossTracker:
    """Minimal loss tracker stub."""

    def get_size_modifier(self):
        return 1.0


class DummyMindMath:
    """Minimal mind math stub."""

    async def _tool_validate_geometry(self, **kwargs):
        return {"valid": True, "score": 1.0}


class DummyEntropyCalc:
    """Minimal entropy calc stub."""

    def signal_entropy(self, p_before: float, p_after: float) -> float:
        return 0.1

    def entropy_modifier(self, base_lambda: int, entropy_score: float) -> int:
        return base_lambda + 5


class DummyBudgetMonitor:
    """Minimal budget monitor stub."""

    def can_trade(self, symbol: str, risk: float) -> bool:
        return True

    def is_trading_allowed(self, *args) -> bool:
        return True


class DummyLiveLearner:
    """Minimal live learner stub."""

    _n_trades = 0
    _matrix = {}

    def evaluate_proposal(self, *args, **kwargs):
        return {"agent": "Agent_D", "vote": "YES", "confidence": 0.7, "reason": "dummy"}


class DummyAgent:
    """Generic agent that always votes YES."""

    def __init__(self, name: str = "Dummy"):
        self.name = name

    def evaluate_proposal(self, *args, **kwargs):
        return {"agent": self.name, "vote": "YES", "confidence": 0.7, "reason": "dummy"}


class DummyDecisionEngine:
    """Minimal decision engine that always approves."""

    async def evaluate(self, context, votes):
        return {
            "decision": "EXECUTE",
            "confidence": 0.7,
            "reason": "dummy approval",
            "votes": votes,
        }


class DummyTaskManager:
    """Minimal task manager stub."""

    def spawn_trade(self, symbol, pattern_dict):
        class Task:
            id = "dummy-task"

            def set_phase(self, *args):
                pass

            def log(self, *args):
                pass

            def finalize(self, *args):
                pass

            def transition(self, *args):
                pass

        return Task()


class DummyBrain:
    """Minimal brain stub for TradingCoordinator."""

    def __init__(self):
        self.mode = "paper"
        self.active_broker = "ibkr"
        self.current_regime = "TRENDING"
        self.bus = None
        self.db_path = "data/trading.db"
        self._oracle_freeze = False
        self._oracle_risk_modifier = 1.0
        self._oracle_dhatu = "Sthira"
        self.session_pnl = 0.0
        self.positions = []
        self._vetting_cooldowns = {}
        self._learned_win_rates = {}
        self.skill_tree = DummySkillTree()
        self.vault = None
        # Coordinator pulls these from the brain; provide real instances.
        self.regime_router = RegimeStrategyRouter()
        self.confluence_engine = ConfluenceEngine()
        self.adaptive_engine = LiveAdaptiveEngine()
        self.governance_engine = NeuralGovernanceEngine()
        self.trade_interrogator = DummyTradeInterrogator()
        self.ibkr_sizer = DummySizer()
        self.regime_classifier = DummyRegimeClassifier()
        self.ibkr_drawdown = DummyDrawdownModifier()
        self.loss_tracker = DummyLossTracker()
        self.mind_math = DummyMindMath()
        self.entropy_calc = DummyEntropyCalc()
        self.budget_monitor = DummyBudgetMonitor()
        self.live_learner = DummyLiveLearner()
        self.escape_classifier = None
        self.mtf_aligner = None
        self.sovereign_atlas = None
        self.dhatu_oracle = None
        self.neural_engine = None
        self.regime_classifier_neural = None
        self.agent_b = DummyAgent("Agent_B")
        self.agent_c = DummyAgent("Agent_C")
        self.agent_d = DummyAgent("Agent_D")
        self.agent_e = DummyAgent("Agent_E")
        self.risk_guard = DummyAgent("Risk_Guard")
        self.agent_g = DummyAgent("Agent_G")
        self.agent_h = DummyAgent("Agent_H")
        self.decision_engine = DummyDecisionEngine()
        self.task_manager = DummyTaskManager()

    def __getattr__(self, name: str) -> Any:
        # Satisfy any remaining brain attribute lookups with safe defaults.
        return None

    async def _get_daily_pnl(self, account_type: str) -> float:
        return 0.0

    async def get_safe_buying_power(self, account_type: str) -> float:
        return 50000.0

    async def _fetch_ohlcv(self, symbol: str, timeframe: str = "1m"):
        n = 100
        base = 100.0
        prices = [base + i * 0.01 for i in range(n)]
        return pl.DataFrame(
            {
                "timestamp": list(range(n)),
                "open": prices,
                "high": [p + 0.05 for p in prices],
                "low": [p - 0.05 for p in prices],
                "close": prices,
                "volume": [1000] * n,
            }
        )

    async def get_current_spread(self, symbol: str):
        return {"bid": 99.99, "ask": 100.01, "spread": 0.02}

    async def _get_vix(self) -> float:
        return 18.0


async def main() -> None:
    print("=== Dummy Trade Test ===")
    print("Mode:", os.environ.get("TRADING_MODE"))

    brain = DummyBrain()
    bridge = DummyBridge()
    coordinator = TradingCoordinator(bridge, brain)

    symbol = "DUMMY"
    pattern = make_pattern()

    proposal = {
        "pattern": pattern,
        "task": None,
    }

    result = await coordinator.initiate_trade_lifecycle(symbol, proposal, is_probe=True)
    print(f"Coordinator result: {result}")

    # Check database for trade record
    db_path = Path("data/trading.db")
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM trades WHERE instrument = ? AND date(timestamp) = date('now')",
            (symbol,),
        )
        count = cur.fetchone()[0]
        print(f"Trade records created for {symbol} today: {count}")
        cur.execute(
            "SELECT instrument, direction, entry_price, shares, broker, outcome FROM trades WHERE instrument = ? ORDER BY timestamp DESC LIMIT 1",
            (symbol,),
        )
        row = cur.fetchone()
        if row:
            print("Last trade:", row)
        conn.close()
    else:
        print(f"Database not found at {db_path}")


if __name__ == "__main__":
    asyncio.run(main())
