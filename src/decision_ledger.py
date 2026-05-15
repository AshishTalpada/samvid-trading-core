"""
src/decision_ledger.py — Sovereign Decision Audit Trail

Append-only structured log that records EVERY trade decision:
who triggered it, what each agent voted, and the final outcome.

Usage:
    from decision_ledger import LEDGER

    # At pattern discovery:
    LEDGER.record_entry(symbol, pattern, agent_votes, consensus)

    # At position exit:
    LEDGER.record_exit(symbol, exit_type, pnl, r_multiple, triggered_by)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("DecisionLedger")

_DB_PATH = Path(__file__).parent.parent / "data" / "decision_ledger.db"


@dataclass
class LedgerEntry:
    timestamp: str
    event_type: str  # "ENTRY" | "EXIT" | "VETO" | "FALLBACK"
    symbol: str
    action: str  # "BUY" | "SELL" | "HOLD" | "BLOCKED"
    triggered_by: str  # which agent/mind initiated this
    agent_votes: dict  # {"agent_a": "BUY (reason)", "agent_b": "HOLD", ...}
    pattern: str = ""
    pattern_confidence: float = 0.0
    pnl_usd: float = 0.0
    r_multiple: float = 0.0
    exit_type: str = ""
    override: str = ""  # "RISK_VETO", "DLQ_ESCALATION", "FALLBACK_MODE", etc.
    meta: dict = field(default_factory=dict)


class DecisionLedger:
    """
    Thread-safe, append-only audit log for every trade decision.

    Writes to a dedicated SQLite file (not the main trades DB) using
    WAL mode for zero contention. Exposes the last N entries via
    `recent()` for the dashboard endpoint.
    """

    def __init__(self, db_path: Path = _DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

        import queue
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        """Single background thread consuming the write queue."""
        while True:
            try:
                entry = self._queue.get()
                if entry is None:
                    break
                self._write(entry)
                self._queue.task_done()
            except Exception as e:
                logger.error(f"DecisionLedger Worker Error: {e}")
                time.sleep(1)

    def _init_db(self) -> None:
        """Create the ledger table if it doesn't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ledger (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    symbol      TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    triggered_by TEXT NOT NULL,
                    agent_votes TEXT NOT NULL,
                    pattern     TEXT DEFAULT '',
                    pattern_confidence REAL DEFAULT 0.0,
                    pnl_usd     REAL DEFAULT 0.0,
                    r_multiple  REAL DEFAULT 0.0,
                    exit_type   TEXT DEFAULT '',
                    override    TEXT DEFAULT '',
                    meta        TEXT DEFAULT '{}'
                )
            """)
            conn.commit()
            try:
                # 48 hours ago in nanoseconds
                cutoff = time.time_ns() - (48 * 3600 * 1_000_000_000)
                conn.execute(
                    "DELETE FROM ledger WHERE event_type='VETO' AND timestamp < ?",
                    (str(cutoff),),
                )
                conn.commit()
                conn.execute("VACUUM")
            except Exception:
                pass
        logger.info(f"DecisionLedger: Initialized at {self._db_path}")

    def _write(self, entry: LedgerEntry) -> None:
        """Synchronous write — called by the background worker thread."""
        try:
            with sqlite3.connect(str(self._db_path), timeout=60.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout=60000;")
                conn.execute(
                    """INSERT INTO ledger
                       (timestamp, event_type, symbol, action, triggered_by,
                        agent_votes, pattern, pattern_confidence, pnl_usd,
                        r_multiple, exit_type, override, meta)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        entry.timestamp,
                        entry.event_type,
                        entry.symbol,
                        entry.action,
                        entry.triggered_by,
                        json.dumps(entry.agent_votes),
                        entry.pattern,
                        entry.pattern_confidence,
                        entry.pnl_usd,
                        entry.r_multiple,
                        entry.exit_type,
                        entry.override,
                        json.dumps(entry.meta),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"DecisionLedger: Write failed — {e}")

    def record_entry(
        self,
        symbol: str,
        pattern: str,
        confidence: float,
        agent_votes: dict[str, str],
        triggered_by: str = "agent_a",
        override: str = "",
        meta: dict | None = None,
        event_type: str = "ENTRY",
    ) -> None:
        """Record a new trade entry or execution decision."""
        entry = LedgerEntry(
            timestamp=str(time.time_ns()),
            event_type=event_type,
            symbol=symbol,
            action="BUY" if event_type in ["ENTRY", "EXECUTION"] else "BLOCKED",
            triggered_by=triggered_by,
            agent_votes=agent_votes,
            pattern=pattern,
            pattern_confidence=confidence,
            override=override,
            meta=meta or {},
        )
        self._queue.put(entry)
        logger.info(
            f"LEDGER ENTRY [{symbol}] — {pattern} ({confidence:.1f}%) "
            f"| Votes: {agent_votes} | Override: {override or 'None'}"
        )

    def record_exit(
        self,
        symbol: str,
        exit_type: str,
        pnl_usd: float,
        r_multiple: float,
        triggered_by: str = "exit_intelligence",
        agent_votes: dict[str, str] | None = None,
        override: str = "",
        meta: dict | None = None,
    ) -> None:
        """Record a position exit decision."""
        action = "WIN" if pnl_usd >= 0 else "LOSS"
        entry = LedgerEntry(
            timestamp=str(time.time_ns()),
            event_type="EXIT",
            symbol=symbol,
            action=action,
            triggered_by=triggered_by,
            agent_votes=agent_votes or {},
            exit_type=exit_type,
            pnl_usd=round(pnl_usd, 2),
            r_multiple=round(r_multiple, 3),
            override=override,
            meta=meta or {},
        )
        self._queue.put(entry)
        logger.info(
            f"LEDGER EXIT [{symbol}] — {exit_type} | PnL: ${pnl_usd:+.2f} "
            f"| R: {r_multiple:.2f}x | By: {triggered_by}"
        )

    def record_veto(
        self,
        symbol: str,
        reason: str,
        triggered_by: str,
        meta: dict | None = None,
    ) -> None:
        """Record a blocked/vetoed trade decision."""
        entry = LedgerEntry(
            timestamp=str(time.time_ns()),
            event_type="VETO",
            symbol=symbol,
            action="BLOCKED",
            triggered_by=triggered_by,
            agent_votes={},
            override=reason,
            meta=meta or {},
        )
        self._queue.put(entry)
        logger.info(f"LEDGER VETO [{symbol}] — {reason} | By: {triggered_by}")

    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        """Return the last N ledger entries for the dashboard."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (n,)
                ).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["agent_votes"] = json.loads(d.get("agent_votes", "{}"))
                d["meta"] = json.loads(d.get("meta", "{}"))
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"DecisionLedger: Read failed — {e}")
            return []

    def summary_stats(self) -> dict[str, Any]:
        """Aggregate stats for the dashboard — total wins, losses, avg R."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                row = conn.execute("""
                    SELECT
                        COUNT(*) as total_decisions,
                        SUM(CASE WHEN event_type='EXIT' AND pnl_usd >= 0 THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN event_type='EXIT' AND pnl_usd < 0 THEN 1 ELSE 0 END)
                        as losses,
                        SUM(CASE WHEN event_type='VETO' THEN 1 ELSE 0 END) as vetos,
                        ROUND(AVG(CASE WHEN event_type='EXIT' THEN r_multiple END), 3) as avg_r,
                        ROUND(SUM(CASE WHEN event_type='EXIT' THEN pnl_usd ELSE 0 END), 2)
                        as total_pnl
                    FROM ledger
                """).fetchone()
            return {
                "total_decisions": row[0],
                "wins": row[1] or 0,
                "losses": row[2] or 0,
                "vetos": row[3] or 0,
                "avg_r_multiple": row[4] or 0.0,
                "total_pnl_usd": row[5] or 0.0,
            }
        except Exception as e:
            logger.error(f"DecisionLedger: Stats failed — {e}")
            return {}


# Module-level singleton — import from anywhere
LEDGER = DecisionLedger()
