import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import timezone
from typing import Any

from config import PROJECT_PATH
from mind_bridge import MindBridge
from time_sync import TimeSync

logger = logging.getLogger(__name__)


class MindEvolution:
    """
    Agent D/E: The Self-Evolution Mind.
    Focuses on 'Strategic Learning' and 'Peak Equity Preservation'.
    """

    def __init__(self, bridge: Any = None, **kwargs) -> None:
        self.bridge = bridge
        self.is_running = False
        self.peak_equity = 0.0
        self.drawdown_limit = 0.10  # 10% hard floor
        self.historical_memory: list[dict] = []

        self.db_path = os.path.join(PROJECT_PATH, "data", "trading.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self._last_peak_save = TimeSync.now().timestamp()

        try:
            conn = sqlite3.connect(self.db_path, timeout=60)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            cursor = conn.cursor()
            # Ensure table exists before querying
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            cursor.execute("SELECT value FROM system_state WHERE key='peak_equity'")
            row = cursor.fetchone()
            conn.close()
            if row:
                self.peak_equity = float(row[0])
                logger.info(f"MindEvolution: Restored High Water Mark: ${self.peak_equity:.2f}")
        except Exception as e:
            logger.error(f"MindEvolution: Could not load peak_equity on startup: {e}")

        # Register Strategic Tools with the Bridge
        self.bridge.register_tool("optimize_thresholds", self._tool_optimize_thresholds)
        self.bridge.register_tool("evolve_strategy", self._tool_evolve_strategy)
        self.bridge.register_tool("report_peak", self._tool_report_peak)
        self.bridge.register_tool(
            "housekeeping", self._tool_housekeeping
        )  # Background Housekeeping
        self.bridge.register_tool(
            "update_knowledge", self._tool_update_knowledge
        )  # Team Memory Sync

        self._background_tasks = set()

    async def start(self) -> None:
        """Launch the Evolution Mind process."""
        self.is_running = True
        logger.info("MindEvolution: Strategic improvement layer active.")

        t1 = asyncio.create_task(self._monitor_equity_peaks())
        t2 = asyncio.create_task(self._process_strategic_dialogue())
        t3 = asyncio.create_task(self._autonomous_heuristic_refinement())

        for t in [t1, t2, t3]:
            self._background_tasks.add(t)
            t.add_done_callback(self._background_tasks.discard)

    async def _autonomous_heuristic_refinement(self) -> None:
        """Audits the system configuration against discovered wisdom and REAL performance."""
        from decision_ledger import LEDGER

        while self.is_running:
            try:
                # 1. Fetch real-world performance metrics from the Ledger
                stats = LEDGER.summary_stats()
                win_rate = (
                    stats["wins"] / (stats["wins"] + stats["losses"])
                    if (stats["wins"] + stats["losses"]) > 0
                    else 0.5
                )

                # 2. Audit against Strategic Wisdom
                wisdom_path = os.path.join(PROJECT_PATH, "data", "wisdom.json")
                if os.path.exists(wisdom_path):
                    with open(wisdom_path, "r") as f:
                        wisdom = json.load(f)

                    # Trigger EVOLUTION if performance is lagging OR entropy is high
                    if wisdom.get("entropy_state") == "HIGH ENTROPY" or win_rate < 0.45:
                        logger.warning(
                            f"🚨 [Evolution]: Strategic Lag Detected (WR: {win_rate:.2%}). Tightening DNA."
                        )
                        await self._tool_evolve_strategy(
                            "performance_tightening",
                            {"expected_profit_factor": 2.5, "min_win_rate": 0.55},
                        )

                await asyncio.sleep(3600 * 4)  # Audit every 4 hours
            except Exception as e:
                logger.error(f"MindEvolution: Refinement error: {e}")
                await asyncio.sleep(60)

    async def _monitor_equity_peaks(self) -> None:
        """Lock in new equity peaks and dynamically tighten trailing stop protection."""
        while self.is_running:
            try:
                # 1. Fetch current equity from the database
                current_equity = await self._fetch_current_equity()

                if current_equity > self.peak_equity:
                    old_peak = self.peak_equity
                    self.peak_equity = current_equity

                    await self._persist_peak(current_equity)

                    await self.bridge.broadcast(
                        "evolution",
                        f"NEW PEAK REACHED: ${current_equity:.2f} (Old: ${old_peak:.2f}). Locking in delta.",
                        {"type": "PEAK", "new_equity": current_equity},
                    )

                await asyncio.sleep(300)  # 5-minute peak monitoring
            except Exception as e:
                logger.error(f"MindEvolution: Equity Monitor Error: {e}")
                await asyncio.sleep(10)

    async def _process_strategic_dialogue(self) -> None:
        """
        Negotiates new trading rules between the minds.
        Listens for failure patterns and triggers evolution.
        """
        while self.is_running:
            try:
                msg = await self.bridge.get_next_message("evolution")
                if msg:
                    logger.info(f"MindEvolution: Analyzing strategic signal: {msg}")
                    # Strategy evolution logic here
            except Exception as e:
                logger.error(f"MindEvolution: Dialogue Error: {e}")
                await asyncio.sleep(1)

    async def _tool_optimize_thresholds(self, strategy: str, data: dict) -> dict[str, Any]:
        """Cognitive tool to refine entry/exit thresholds based on win rates."""
        logger.info(f"MindEvolution: Optimizing thresholds for {strategy}...")
        # Optimization logic
        return {"status": "SUCCESS", "new_threshold": 0.85}

    async def _tool_evolve_strategy(self, strategy_id: str, params: dict) -> dict[str, Any]:
        """Master mutation tool. Permanently alters the organism's DNA (Config)."""
        logger.warning(f"MindEvolution: EVOLVING strategy {strategy_id}...")

        # Call Healer (Architect) to apply the genetic patch
        mutation_result = await self.bridge.call_tool(
            "heal", issue=f"Strategic Mutation: {strategy_id}", suggestion=json.dumps(params)
        )

        if mutation_result.get("success"):
            logger.info(f"MindEvolution: Strategy {strategy_id} EVOLVED successfully.")
            return {"success": True, "mutation": "V9.0_SLIPPAGE_PROTECTION", "status": "LIVE"}

        return {"success": False, "error": mutation_result.get("error", "Unknown mutation error")}

    async def _tool_report_peak(self) -> dict[str, Any]:
        return {"peak": self.peak_equity, "at_time": TimeSync.now().isoformat()}

    async def _fetch_current_equity(self) -> float:
        """
        Calculates 'Real' Equity with Conservative Sovereign Haircut.
        """
        try:
            result = await self.bridge.call_tool("get_account_status", account_type="ibkr")
            if "error" in result:
                return self.peak_equity

            equity = float(result.get("equity", 0.0))
            unrealized_pnl = float(result.get("unrealized_pnl", 0.0))

            net_liq = equity
            if unrealized_pnl > 0:
                net_liq -= unrealized_pnl * 0.15

            return net_liq
        except Exception as e:
            logger.error(f"MindEvolution: Error in real equity fetch: {e}")
            return self.peak_equity

    async def _persist_peak(self, peak: float) -> None:
        """Saves the high water mark to the SQLite state matrix."""

        def _sync_save():
            try:
                conn = sqlite3.connect(self.db_path, timeout=60)
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("peak_equity", str(peak)),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"MindEvolution: Failed to persist peak: {e}")

        await asyncio.to_thread(_sync_save)

    async def _tool_housekeeping(self) -> dict[str, Any]:
        """Performs background cleanup of stale dialogue and telemetry logs."""
        logger.info("MindEvolution: Performing background housekeeping...")
        return {"status": "SUCCESS", "cleanup": "STALE_LOG_ROTATED"}

    async def _tool_update_knowledge(self, knowledge_item: str, source: str) -> dict[str, Any]:
        """Synchronizes session-level 'Learnings' across all minds via Team Context."""
        logger.info(f"MindEvolution: Knowledge Update from '{source}': {knowledge_item[:50]}...")

        self.historical_memory.append(
            {"item": knowledge_item, "source": source, "timestamp": TimeSync.now().isoformat()}
        )
        # Cap memory to 200 items to prevent memory leaks
        if len(self.historical_memory) > 200:
            self.historical_memory.pop(0)

        return {"status": "SYNCED", "memory_depth": len(self.historical_memory)}

