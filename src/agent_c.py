"""
src/agent_c.py - Evolutionary Intelligence (The Feedback Loop)
This component enables the system to "learn" by:
1. Snapshotting the exact market state (features) when a trade/pattern is detected.
2. Mapping subsequent P&L back to those features.
3. Dynamically adjusting Brain thresholds to optimize for win-rate and Sharpe.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EvolutionManager:
    """
    The Evolutionary Engine (Agent C).
    Manages the feedback loop between trade outcomes and technical/macro parameters.
    """

    def __init__(
        self, db_path: str | None = None, main_db_path: str = "data/trading.db", dms: Any = None
    ) -> None:
        self.main_db_path = main_db_path
        self.dms = dms
        if db_path is None:
            project_root = Path(__file__).resolve().parent.parent
            self.db_path = str(project_root / "data" / "evolution.db")
        else:
            self.db_path = db_path

        self._init_db()
        self.conn = sqlite3.connect(self.db_path, timeout=60.0, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA busy_timeout = 60000;")
        logger.info(f"EvolutionManager initialized at {self.db_path}")

    def _init_db(self) -> None:
        """Initialize the Evolution / Learning database."""
        Path("data").mkdir(exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 60000;")
        cursor = conn.cursor()

        # 1. Decision Snapshots (Features at the time of trade)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                dhatu_state TEXT,
                risk_modifier REAL,
                indicators_json TEXT,  -- RSI, MACD, etc.
                prediction_bias TEXT,  -- BULLISH / BEARISH
                confidence REAL,
                trade_id TEXT UNIQUE   -- Link to 'trades' table in main DB
            )
        """)

        # 2. Parameter Optimization (Learned thresholds)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brain_optimization (
                parameter_name TEXT PRIMARY KEY,
                parameter_value TEXT,
                confidence REAL,
                sharpe_ratio REAL,
                last_updated TEXT
            )
        """)

        conn.commit()
        conn.close()

    def snapshot_decision(
        self,
        symbol: str,
        features: dict[str, Any],
        dhatu_state: str,
        risk_modifier: float = 1.0,
        bias: str = "BUY",
        confidence: float = 0.0,
        trade_id: str | None = None,
    ) -> None:
        """
        Record a 'Decision Snapshot' for future learning reinforcement.
        """
        try:
            cursor = self.conn.cursor()

            cursor.execute(
                """
                INSERT INTO decision_snapshots
                (symbol, timestamp, dhatu_state, risk_modifier, indicators_json, prediction_bias, confidence, trade_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    symbol,
                    datetime.now().isoformat(),
                    dhatu_state,
                    risk_modifier,
                    json.dumps(features),
                    bias,
                    confidence,
                    trade_id,
                ),
            )

            self.conn.commit()
            logger.info(f"EvolutionManager: Snapshot stored for {symbol} (Bias: {bias})")
        except Exception as e:
            logger.error(f"EvolutionManager: Failed to store snapshot: {e}")

    def audit_performance(self, main_db_path: str | None = None) -> dict[str, Any]:
        """
        Analyze recent snapshots vs actual P&L from the main database
        to calculate performance by Dhatu state including Expectancy and Profit Factor.
        """
        if main_db_path is None:
            main_db_path = self.main_db_path

        try:
            from pathlib import Path

            safe_db_path = str(Path(main_db_path).resolve())
            if not Path(safe_db_path).exists():
                logger.error(f"EvolutionManager: Main DB not found at {safe_db_path}")
                return {"error": "Main DB not found"}

            try:
                self.conn.execute(f"ATTACH DATABASE '{safe_db_path}' AS main_db")
            except sqlite3.OperationalError as e:
                if (
                    "already in use" in str(e).lower()
                    or "database main_db is already attached" in str(e).lower()
                ):
                    pass  # Already attached
                else:
                    raise
            cursor = self.conn.cursor()

            # Calculate metrics per Dhatu state (Refined for Expectancy)
            cursor.execute("""
                SELECT
                    s.dhatu_state,
                    COUNT(*) as total,
                    SUM(CASE WHEN t.pnl_dollars > 0 THEN 1 ELSE 0 END) as wins,
                    AVG(t.pnl_dollars) as avg_pnl,
                    SUM(CASE WHEN t.pnl_dollars > 0 THEN t.pnl_dollars ELSE 0 END) as gross_wins,
                    SUM(CASE WHEN t.pnl_dollars < 0 THEN ABS(t.pnl_dollars) ELSE 0 END) as gross_losses
                FROM decision_snapshots s
                JOIN main_db.trades t ON s.trade_id = t.id
                GROUP BY s.dhatu_state
            """)

            rows = cursor.fetchall()
            stats = {}
            best_state = "None"
            best_expectancy = -999.0

            for state, total, wins, _avg_pnl, g_wins, g_losses in rows:
                wr = wins / total if total > 0 else 0.0
                pf = g_wins / g_losses if g_losses > 0 else (g_wins if g_wins > 0 else 1.0)
                expectancy = (wr * (g_wins / wins if wins > 0 else 0)) - (
                    (1 - wr) * (g_losses / (total - wins) if total > wins else 0)
                )

                stats[state] = {
                    "wr": round(wr, 2),
                    "n": total,
                    "pf": round(pf, 2),
                    "expectancy": round(expectancy, 2),
                }

                if expectancy > best_expectancy:
                    best_expectancy = expectancy
                    best_state = state

            # self.conn is persistent; do not close.
            return {
                "dhatu_stats": stats,
                "top_performing_dhatu": best_state,
                "system_state": "analyzing" if stats else "cold_start",
            }
        except Exception as e:
            logger.error(f"EvolutionManager: Performance audit failed: {e}")
            return {"error": str(e), "system_state": "error"}

    def audit_global_performance(self, main_db_path: str | None = None) -> dict[str, Any]:
        """
        Calculates high-level metrics (WinRate, P&L, Sortino, Profit Factor) for the entire system.
        Handles encrypted pnl_dollars values by decrypting in Python.
        """
        if main_db_path is None:
            main_db_path = self.main_db_path
        try:
            from pathlib import Path

            from database_security import DatabaseSecurity

            safe_db_path = str(Path(main_db_path).resolve())
            if not Path(safe_db_path).exists():
                return {"error": "Main DB not found"}

            conn = sqlite3.connect(safe_db_path, timeout=60.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Fetch all trades to handle encryption in application layer
            cursor.execute("SELECT pnl_dollars FROM trades ORDER BY timestamp ASC")
            rows = cursor.fetchall()

            if not rows:
                conn.close()
                return {
                    "n": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "max_drawdown": 0.0,
                    "pf": 0.0,
                    "sortino": 0.0,
                }

            # 2. Decrypt and aggregate
            pnls = []
            gross_wins = 0.0
            gross_losses = 0.0
            wins = 0

            for row in rows:
                val_raw = row["pnl_dollars"]
                if val_raw is None:
                    continue

                try:
                    if isinstance(val_raw, str) and val_raw.startswith("gAAAAA"):
                        p = DatabaseSecurity.decrypt_float(val_raw)
                    else:
                        p = float(val_raw)
                except Exception:
                    continue

                pnls.append(p)
                if p > 0:
                    wins += 1
                    gross_wins += p
                else:
                    gross_losses += abs(p)

            n = len(pnls)
            if n == 0:
                conn.close()
                return {
                    "n": 0,
                    "win_rate": 0.0,
                    "total_pnl": 0.0,
                    "max_drawdown": 0.0,
                    "pf": 0.0,
                    "sortino": 0.0,
                }

            win_rate = wins / n
            profit_factor = gross_wins / gross_losses if gross_losses > 0 else gross_wins

            # 3. Calculate Drawdown
            equity = 500.0
            peak = equity
            max_dd = 0.0
            current_equity = equity

            for p in pnls:
                current_equity += p
                if current_equity > peak:
                    peak = current_equity
                dd = (peak - current_equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd

            # 4. Calculate Advanced Metrics (Sharpe & Sortino)
            sharpe = 0.0
            sortino = 0.0
            if n > 5:
                avg_ret = np.mean(pnls)
                std_ret = np.std(pnls)
                sharpe = (avg_ret / std_ret) if std_ret > 0 else 0.0

                downside_rets = [p for p in pnls if p < 0]
                downside_std = np.std(downside_rets) if downside_rets else 0.0
                sortino = (
                    (avg_ret / downside_std)
                    if downside_std > 0
                    else (sharpe if avg_ret > 0 else 0.0)
                )

            conn.close()
            return {
                "n": n,
                "win_rate": round(win_rate, 4),
                "total_pnl": round(gross_wins - gross_losses, 2),
                "max_drawdown": round(max_dd, 4),
                "pf": round(profit_factor, 2),
                "sharpe": round(sharpe, 2),
                "sortino": round(sortino, 2),
            }
        except Exception as e:
            logger.error(f"EvolutionManager: Global audit failed: {e}")
            return {"error": str(e)}

    def evolve_parameters(self) -> list[tuple[str, float, float, float]]:
        """
        Proposes mutations for system parameters based on global audit.
        Uses Sortino Ratio and Profit Factor for higher fidelity decisions.
        """
        import config
        from risk_invariants import RiskInvariants

        insights = self.audit_global_performance()
        if "error" in insights or insights.get("n", 0) < 10:
            return []  # Need at least 10 trades to evolve

        mutations = []
        insights["win_rate"]
        dd = insights["max_drawdown"]
        sortino = insights.get("sortino", 0.0)
        pf = insights.get("pf", 0.0)

        # Strategy 1: System Max Risk Calibration
        current_risk = getattr(config, "SYSTEM_MAX_RISK", 0.04)
        new_risk = current_risk

        # If we are winning hard (Sortino > 1.0, PF > 1.5) we expand risk
        if sortino > 1.0 and pf > 1.5 and dd < 0.05:
            new_risk = round(current_risk + 0.005, 4)
        # If we are bleeding (PF < 1.0) or drawdown is dangerous, hit the brakes
        elif pf < 1.0 or dd > 0.08:
            new_risk = round(current_risk - 0.01, 4)

        bounds = RiskInvariants.SANCTITY_BOUNDS.get("SYSTEM_MAX_RISK")
        if bounds:
            new_risk = max(bounds.min_val, min(bounds.max_val, new_risk))

        if new_risk != current_risk:
            if RiskInvariants.is_mutation_safe("SYSTEM_MAX_RISK", new_risk):
                mutations.append(("SYSTEM_MAX_RISK", current_risk, new_risk, sortino))

        # Strategy 2: Exit Threshold Tuning
        current_exit = getattr(config, "BELIEF_EXIT_THRESHOLD", 0.35)
        new_exit = current_exit

        # If profit factor is low, tighten exits. If very high, allow more breathing room.
        if sortino < 0.5 or pf < 1.2:
            new_exit = round(current_exit - 0.05, 2)
        elif sortino > 1.5 and pf > 2.0:
            new_exit = round(current_exit + 0.05, 2)

        e_bounds = RiskInvariants.SANCTITY_BOUNDS.get("BELIEF_EXIT_THRESHOLD")
        if e_bounds:
            new_exit = max(e_bounds.min_val, min(e_bounds.max_val, new_exit))

        if new_exit != current_exit:
            if RiskInvariants.is_mutation_safe("BELIEF_EXIT_THRESHOLD", new_exit):
                mutations.append(("BELIEF_EXIT_THRESHOLD", current_exit, new_exit, sortino))

        return mutations

    def _apply_mutation(self, key: str, value: float, sharpe: float = 0.0) -> None:
        """Persists mutation to both runtime config and optimization database."""
        import config

        try:
            # 1. Update Runtime Memory
            setattr(config, key, value)

            # 2. Persist to DB
            try:
                conn = sqlite3.connect(self.db_path, timeout=60.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout = 60000;")
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO brain_optimization (parameter_name, parameter_value, confidence, sharpe_ratio, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (key, str(value), 1.0, sharpe, datetime.now().isoformat()),
                )
                conn.commit()
                conn.close()

                logger.warning(f"🧬 MUTATION APPLIED: {key} is now {value}. System has evolved.")
            except Exception as e:
                logger.error(f"EvolutionManager: Failed to apply mutation {key}: {e}")
        except Exception as e:
            logger.error(f"EvolutionManager: Failed to apply mutation {key}: {e}")

    def load_optimizations(self) -> None:
        """
        Loads all previously optimized parameters from the database and
        injects them into the global config module. This ensures evolutionary
        gains persist across system restarts.
        """
        import config

        try:
            conn = sqlite3.connect(self.db_path, timeout=60.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT parameter_name, parameter_value FROM brain_optimization")
            rows = cursor.fetchall()

            restored_count = 0
            for row in rows:
                key = row["parameter_name"]
                val = float(row["parameter_value"])

                # Double-check safety even on load (prevents corruption at rest)
                from risk_invariants import RiskInvariants

                if hasattr(config, key) and RiskInvariants.is_mutation_safe(key, val):
                    setattr(config, key, val)
                    restored_count += 1
                else:
                    logger.error(
                        f"EvolutionManager: Safety VETO during startup load for {key}={val}"
                    )

            conn.close()
            if restored_count > 0:
                logger.info(
                    f"✅ Evolution: Restored {restored_count} optimized parameters from persistent memory."
                )
        except Exception as e:
            logger.error(f"EvolutionManager: Failed to load optimizations: {e}")

    async def run_evolution_cycle(self) -> None:
        """Continuous background task to refine system parameters."""
        logger.info("Evolution: Recursive Feedback loop active (1-hour pulse).")
        while True:
            try:
                if self.dms:
                    self.dms.record_heartbeat("AGENT_C")

                # 1. Perform Audits
                dhatu_insights = self.audit_performance()
                if dhatu_insights.get("top_performing_dhatu") != "None":
                    logger.info(
                        f"Evolution: Peak State Alpha: {dhatu_insights['top_performing_dhatu']}"
                    )

                # 2. Propose & Apply Mutations
                mutations = self.evolve_parameters()
                for key, old_v, new_v, sharpe in mutations:
                    logger.info(
                        f"Evolution: Proposing mutation {key}: {old_v} -> {new_v} (Sharpe: {sharpe})"
                    )
                    self._apply_mutation(key, new_v, sharpe)

                if not mutations:
                    logger.debug("Evolution: Cycle complete. Stability maintained.")

            except Exception as e:
                logger.error(f"EvolutionManager cycle failed: {e}")

            await asyncio.sleep(3600)  # Check every hour
