from __future__ import annotations

# ruff: noqa: E402, I001

import asyncio
import json
import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import coordinator as coordinator_mod
from agent_a import PatternResult
from coordinator import TradingCoordinator


LOG_PATH = ROOT / "logs" / "offline_execution_replay.log"
DB_PATH = ROOT / "tmp" / "offline_execution_replay.db"


def _setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PATH, encoding="utf-8"), logging.StreamHandler()],
    )


def _build_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    schema = (ROOT / "data" / "schema.sql").read_text(encoding="utf-8")
    conn.executescript(schema)
    conn.execute(
        "INSERT INTO vix_data (timestamp, vix) VALUES (?, ?)",
        (datetime.now(timezone.utc).isoformat(), 18.0),
    )
    conn.commit()
    return conn


def _vote(
    agent: str, choice: str = "YES", confidence: float = 0.82, reason: str = "offline replay"
):
    return {
        "agent": agent,
        "vote": choice,
        "confidence": confidence,
        "reason": reason,
        "timestamp": time.time_ns(),
    }


async def _build_brain(conn: sqlite3.Connection) -> SimpleNamespace:
    brain = SimpleNamespace()
    brain.db_conn = conn
    brain.active_broker = "IBKR"
    brain.current_regime = "BULL"
    brain.mode = "ibkr_paper"
    brain.positions = []
    brain._state_lock = asyncio.Lock()
    brain._oracle_dhatu = "Samyoga"
    brain._last_fresh_bar_at = {
        symbol: time.monotonic() for symbol in ("SPY", "QQQ", "IWM")
    }

    async def fake_order(symbol, direction, shares, **kwargs):
        return f"SIM-{symbol}-{direction}-{int(shares)}"

    async def fake_log_trade_entry(pos):
        conn.execute(
            """
            INSERT INTO trades (
                timestamp, instrument, direction, pattern, regime, entry_price,
                stop_price, target_price, shares, r_r_ratio, catalyst_score,
                dhatu_state, belief_at_entry, broker, account_id, trading_mode,
                outcome, commission, slippage, net_pnl, intel_snapshot
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pos.entry_time.isoformat(),
                pos.symbol,
                "LONG" if pos.qty > 0 else "SHORT",
                pos.pattern,
                pos.regime_at_entry,
                pos.entry_price,
                pos.stop_loss,
                pos.take_profit,
                abs(pos.qty),
                pos.r_r_ratio,
                pos.catalyst_score,
                pos.dhatu_state,
                pos.initial_belief,
                pos.account_type,
                pos.account_id,
                brain.mode,
                pos.status,
                pos.commission_cost,
                pos.slippage_cost,
                0.0,
                json.dumps({"offline_replay": True}),
            ),
        )
        conn.commit()

    brain._place_ibkr_order = fake_order
    brain._log_trade_entry = fake_log_trade_entry
    return brain


async def _run_case(
    coordinator: TradingCoordinator,
    name: str,
    *,
    symbol: str,
    decision: dict,
    votes: list[dict],
) -> dict:
    brain = coordinator.brain

    pattern = PatternResult(
        name=f"OFFLINE_REPLAY_{name}",
        category="SCALP",
        confidence=88.0,
        entry=106.0,
        stop=104.0,
        target=112.0,
        r_r_ratio=3.0,
        confirmed=True,
        lambda_val=80,
        atr=1.2,
    )

    before_positions = len(brain.positions)
    ok = await coordinator._execute_decision(
        symbol, decision, pattern, votes, is_probe=False, shares=25, task=None
    )
    after_positions = len(brain.positions)
    rows = brain.db_conn.execute(
        "SELECT outcome, COUNT(*) FROM trades GROUP BY outcome ORDER BY outcome"
    ).fetchall()
    rejection_rows = brain.db_conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='decision_rejections'"
    ).fetchone()[0]
    return {
        "case": name,
        "symbol": symbol,
        "success": bool(ok),
        "positions_delta": after_positions - before_positions,
        "positions_total": after_positions,
        "trade_outcomes": rows,
        "decision_rejections_table": bool(rejection_rows),
    }


async def main() -> int:
    _setup_logging()
    conn = _build_db()
    brain = await _build_brain(conn)
    coordinator_mod.send_telegram_alert = lambda *_args, **_kwargs: asyncio.sleep(0, result=True)
    coordinator = TradingCoordinator(MagicMock(), brain)
    results = []
    try:
        base_votes = [
            _vote("Agent_A", "YES", 0.88),
            _vote("Agent_B"),
            _vote("Agent_C"),
            _vote("Risk_Guard", "YES", 0.9),
            _vote("Agent_D", "YES", 0.72),
            _vote("Agent_E"),
            _vote("Agent_F"),
            _vote("Agent_G"),
            _vote("Dhatu_Oracle", "YES", 0.84),
            _vote("Swarm_Predictor", "YES", 0.76),
        ]
        results.append(
            await _run_case(
                coordinator,
                "strong_quorum",
                symbol="SPY",
                decision={"decision": "EXECUTE", "confidence": 0.82, "reason": "offline pass"},
                votes=base_votes + [_vote("Mind_Ultrathink", "YES", 0.78)],
            )
        )
        results.append(
            await _run_case(
                coordinator,
                "cognitive_near_miss",
                symbol="QQQ",
                decision={
                    "decision": "REJECT",
                    "confidence": 0.55,
                    "reason": "COGNITIVE HARD VETO: synthetic near miss",
                },
                votes=base_votes + [_vote("Mind_Ultrathink", "NO", 0.45)],
            )
        )
        results.append(
            await _run_case(
                coordinator,
                "hard_risk_veto",
                symbol="IWM",
                decision={
                    "decision": "REJECT",
                    "confidence": 0.2,
                    "reason": "RISK HARD VETO: synthetic hard risk fail",
                },
                votes=[
                    *_vote_list_without(base_votes, "Risk_Guard"),
                    _vote("Risk_Guard", "NO", 0.0, "hard risk replay"),
                    _vote("Mind_Ultrathink", "YES", 0.78),
                ],
            )
        )
        print(json.dumps({"db": str(DB_PATH), "log": str(LOG_PATH), "results": results}, indent=2))
        return 0
    finally:
        conn.close()


def _vote_list_without(votes: list[dict], agent: str) -> list[dict]:
    return [vote for vote in votes if vote.get("agent") != agent]


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
