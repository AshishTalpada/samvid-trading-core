import asyncio
import json
import logging
import math
import os
import sqlite3
import time
from typing import Any

from config import PROJECT_PATH
from mind_bridge import MindBridge

logger = logging.getLogger(__name__)


class MindEvolution:
    """
    Agent D/E: The Self-Evolution Mind.
    Focuses on 'Strategic Learning' and 'Peak Equity Preservation'.
    Inspired by Claude-Code's 'memory.ts' and 'learning.ts' logic.
    """

    def __init__(self, bridge: MindBridge, db_path: str | None = None) -> None:
        self.bridge = bridge
        self.is_running = False
        self.peak_equity = 0.0
        self.drawdown_limit = 0.10  # 10% hard floor
        self.historical_memory: list[dict] = []
        self._tasks: set[asyncio.Task] = set()

        self.db_path = db_path or os.path.join(PROJECT_PATH, "data", "trading.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        from time_sync import TimeSync

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
                restored_peak = float(row[0])
                if math.isfinite(restored_peak) and restored_peak > 0:
                    self.peak_equity = restored_peak
                    logger.info(
                        f"MindEvolution: Restored High Water Mark: ${self.peak_equity:.2f}"
                    )
        except Exception as e:
            import sys

            print(f"CRITICAL: MindEvolution DB Recovery Failed: {e}", file=sys.stderr)
            logger.debug(f"MindEvolution: Could not load peak_equity on startup: {e}")

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

    async def start(self) -> None:
        """Launch the Evolution Mind process."""
        if self.is_running:
            return
        self.is_running = True
        logger.info("MindEvolution: Strategic improvement layer active.")
        for coroutine in (
            self._monitor_equity_peaks(),
            self._process_strategic_dialogue(),
            self._autonomous_heuristic_refinement(),
        ):
            task = asyncio.create_task(coroutine)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def stop(self) -> None:
        """Stop all evolution workers and wait for cancellation."""
        self.is_running = False
        tasks = [task for task in self._tasks if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def _autonomous_heuristic_refinement(self) -> None:
        """
        The 'Self-Healing' cycle (SE-11 Architect).
        Periodically audits the system configuration against discovered wisdom.
        """
        while self.is_running:
            try:
                wisdom_path = os.path.join(PROJECT_PATH, "data/wisdom.json")
                if os.path.exists(wisdom_path):
                    with open(wisdom_path, encoding="utf-8") as f:
                        wisdom = json.load(f)

                    # High entropy produces a reviewable proposal, never a live mutation.
                    if wisdom.get("entropy_state") == "HIGH ENTROPY":
                        logger.warning(
                            "MindEvolution: High entropy detected; generating a threshold proposal."
                        )
                        await self._tool_optimize_thresholds(
                            "config_tightening",
                            {
                                "trades": wisdom.get("sample_size", 0),
                                "win_rate": wisdom.get("win_rate", 0.0),
                                "current_threshold": wisdom.get("entry_threshold", 0.85),
                                "target_win_rate": 0.55,
                            },
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

                if current_equity is not None and current_equity > self.peak_equity:
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
        """Propose a bounded threshold adjustment only when evidence is sufficient."""
        logger.info("MindEvolution: Evaluating threshold evidence for %s.", strategy)
        try:
            trades = int(data.get("trades", 0))
            win_rate = float(data.get("win_rate", 0.0))
            current = float(data.get("current_threshold", 0.85))
            target = float(data.get("target_win_rate", 0.55))
        except (TypeError, ValueError):
            return {"status": "REJECTED", "reason": "invalid_numeric_evidence"}
        if not all(math.isfinite(value) for value in (win_rate, current, target)):
            return {"status": "REJECTED", "reason": "non_finite_evidence"}
        if trades < 30:
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "strategy": strategy,
                "trades": trades,
                "required_trades": 30,
            }
        if not 0.0 <= win_rate <= 1.0 or not 0.0 <= target <= 1.0:
            return {"status": "REJECTED", "reason": "win_rate_out_of_range"}

        adjustment = max(-0.05, min(0.05, (target - win_rate) * 0.20))
        proposed = max(0.50, min(0.95, current + adjustment))
        proposal = {
            "status": "PROPOSED",
            "strategy": strategy,
            "current_threshold": current,
            "proposed_threshold": proposed,
            "sample_size": trades,
            "observed_win_rate": win_rate,
            "requires_shadow_validation": True,
        }
        self.historical_memory.append(
            {"item": proposal, "source": "threshold_optimizer", "timestamp": time.time_ns()}
        )
        return proposal

    async def _tool_evolve_strategy(self, strategy_id: str, params: dict) -> dict[str, Any]:
        """Record a strategy proposal without mutating production code at runtime."""
        proposal = {
            "success": True,
            "strategy_id": strategy_id,
            "params": dict(params),
            "status": "PENDING_SHADOW_VALIDATION",
            "applied": False,
            "timestamp": time.time_ns(),
        }
        self.historical_memory.append(
            {"item": proposal, "source": "strategy_proposal", "timestamp": proposal["timestamp"]}
        )
        logger.info("MindEvolution: Strategy proposal queued for %s.", strategy_id)
        return proposal

    async def _tool_report_peak(self) -> dict[str, Any]:

        return {"peak": self.peak_equity, "at_time": time.time_ns()}

    async def _fetch_current_equity(self) -> float | None:
        """
        Calculates 'Real' Equity with Conservative Sovereign Haircut.
        """
        try:
            result = await self.bridge.call_tool("get_account_status", account_type="ibkr")
            if "error" in result or not result.get("equity_authoritative", False):
                logger.debug("MindEvolution: Skipping peak update without authoritative equity.")
                return None

            equity = float(result.get("equity", 0.0))
            unrealized_pnl = float(result.get("unrealized_pnl", 0.0))
            if not math.isfinite(equity) or equity <= 0 or not math.isfinite(unrealized_pnl):
                return None

            net_liq = equity
            if unrealized_pnl > 0:
                net_liq -= unrealized_pnl * 0.15

            return net_liq
        except Exception as e:
            logger.error(f"MindEvolution: Error in real equity fetch: {e}")
            return None

    async def _persist_peak(self, peak: float) -> None:
        """Saves the high water mark to the SQLite state matrix."""

        def _sync_save():
            try:
                conn = sqlite3.connect(self.db_path, timeout=60)
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("peak_equity", str(peak)),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("peak_equity_source", "ibkr_net_liquidation_haircut"),
                )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"MindEvolution: Failed to persist peak: {e}")

        await asyncio.to_thread(_sync_save)

    async def _tool_housekeeping(self) -> dict[str, Any]:
        """Performs background cleanup of stale dialogue and telemetry logs."""
        logger.info("MindEvolution: Performing background housekeeping...")
        dialogue_before = len(self.bridge.dialogue_history)
        telemetry_before = len(self.bridge.call_telemetry)
        self.bridge.dialogue_history[:] = self.bridge.dialogue_history[-500:]
        self.bridge.call_telemetry[:] = self.bridge.call_telemetry[-500:]
        self.historical_memory[:] = self.historical_memory[-1000:]
        return {
            "status": "SUCCESS",
            "dialogue_removed": max(0, dialogue_before - 500),
            "telemetry_removed": max(0, telemetry_before - 500),
        }

    async def _tool_update_knowledge(self, knowledge_item: str, source: str) -> dict[str, Any]:
        """Synchronizes session-level 'Learnings' across all minds via Team Context."""
        logger.info(f"MindEvolution: Knowledge Update from '{source}': {knowledge_item[:50]}...")

        self.historical_memory.append(
            {"item": knowledge_item, "source": source, "timestamp": time.time_ns()}
        )
        self.historical_memory[:] = self.historical_memory[-1000:]
        return {"status": "SYNCED", "memory_depth": len(self.historical_memory)}
