import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict

from config import PROJECT_PATH
from vault import Vault  # pyre-ignore[21]

logger = logging.getLogger(__name__)


class SessionRestorer:
    """
    Quantum Session Restoration (Samvid v1.0-beta-beta).
    Inspired by Claude-Code's tmuxSocket.ts and terminalPanel.ts.
    Allows for 'State Freezing' and 'Thawing' of the cognitive process.
    """

    def __init__(self, path: str = os.path.join(PROJECT_PATH, ".session.bin")) -> None:
        self.path = path
        self.last_frozen: datetime | None = None
        self.state_hash: str | None = None

        # Security: Signed session verification (GAP-26 FIX)
        # We NO LONGER use a hardcoded default in production.
        self.secret_key = Vault.get("SESSION_SECRET")
        if not self.secret_key:
            logger.critical("SECURITY BREACH: SESSION_SECRET not found in Vault. Persistence is DISABLED to prevent forgery.")
            raise RuntimeError("Critical Security Configuration Missing: SESSION_SECRET")

    def freeze_state(self, state: dict[str, Any]) -> bool:
        """Serializes and signs the current 'Brain State' for persistent recovery."""
        from time_sync import TimeSync
        try:
            # 1. Prepare State Bundle
            now_ts = TimeSync.now()
            bundle = {"timestamp": now_ts.isoformat(), "state": state, "version": "6.0"}

            # 2. Serialize and Sign (GAP-26 FIX: Using JSON instead of Pickle)
            data = json.dumps(bundle, default=str).encode('utf-8')
            signature = hashlib.sha256(data + self.secret_key.encode()).hexdigest()

            # 3. Write Atomic (Safe-Write pattern)
            temp_path = f"{self.path}.tmp"
            # GAP-176 FIX: Restricted permissions (User-only read/write)
            fd = os.open(temp_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
                f.write(b"\n--SIGNATURE--\n")
                f.write(signature.encode())
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, self.path)
            self.last_frozen = now_ts
            logger.info(
                f"SessionRestorer: State FROZEN at {self.last_frozen.isoformat()}. Size: {len(data)} bytes."
            )
            return True
        except Exception as e:
            logger.error(f"SessionRestorer: Freeze Error: {e}")
            return False

    def record_transcript(self, messages: list[dict[str, Any]]) -> bool:
        """PILLAR 6: Transcript Persistence (9.99 Upgrade)
        Saves a full conversation transcript for resumable sessions.
        """
        from time_sync import TimeSync
        transcript_dir = os.path.join(PROJECT_PATH, "data", "transcripts")
        os.makedirs(transcript_dir, exist_ok=True)

        timestamp = TimeSync.now().strftime("%Y%m%d_%H%M%S")
        transcript_path = os.path.join(transcript_dir, f"session_{timestamp}.json")

        try:
            with open(transcript_path, "w", encoding="utf-8") as f:
                json.dump(messages, f, indent=4, default=str)
            logger.info(f"💾 Restorer: Transcript recorded -> session_{timestamp}.json")
            return True
        except Exception as e:
            logger.error(f"Restorer: Failed to record transcript: {e}")
            return False

    def make_file_snapshot(self, filepath: str) -> str:
        """PILLAR 6: File History Snapshots (9.99 Upgrade)
        Creates a versioned backup before surgical system edits.
        """
        from time_sync import TimeSync
        if not os.path.exists(filepath):
            return ""

        history_dir = os.path.join(PROJECT_PATH, "data", "history")
        os.makedirs(history_dir, exist_ok=True)

        timestamp = TimeSync.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(filepath)
        snapshot_path = os.path.join(history_dir, f"{filename}_{timestamp}.bak")

        import shutil

        try:
            shutil.copy2(filepath, snapshot_path)
            logger.info(
                f"🛡 Restorer: Snapshot created for {filename} -> {os.path.basename(snapshot_path)}"
            )
            return snapshot_path
        except Exception as e:
            logger.error(f"Restorer: Snapshot failed: {e}")
            return ""

    def thaw_state(self) -> dict[str, Any] | None:
        """Verifies and restores the 'Brain State' from the last known good freeze."""
        if not os.path.exists(self.path):
            logger.warning("SessionRestorer: No previous state found to THAW.")
            return None

        try:
            with open(self.path, "rb") as f:
                content = f.read()

            # Split data and signature
            parts = content.split(b"\n--SIGNATURE--\n")
            if len(parts) != 2:
                logger.error("SessionRestorer: State file CORRUPTED (missing signature).")
                return None

            data, signature = parts[0], parts[1].decode()

            # Verify Integrity
            expected_signature = hashlib.sha256(data + self.secret_key.encode()).hexdigest()
            if signature != expected_signature:
                logger.critical(
                    "SECURITY ALERT: Session state signature MISMATCH. Potential tampering detected."
                )
                return None

            bundle = json.loads(data.decode('utf-8'))
            logger.info(
                f"SessionRestorer: State THAWED from {bundle['timestamp']}. Version: {bundle['version']}"
            )
            return bundle["state"]
        except Exception as e:
            logger.error(f"SessionRestorer: Thaw Error: {e}")
            return None

    def save_cognitive_capsule(self, state: Dict[str, Any]) -> None:
        """Samvid v1.0-beta-beta: Persists the Short-Term 'Vibe' of the market."""
        from time_sync import TimeSync
        try:
            capsule_path = "data/cognitive_capsule.json"
            os.makedirs(os.path.dirname(capsule_path), exist_ok=True)
            with open(capsule_path, "w") as f:
                json.dump({
                    "timestamp": TimeSync.now().isoformat(),
                    "payload": state
                }, f, indent=4)
        except Exception as e:
            logger.error(f"SessionRestorer: Failed to save capsule: {e}")

    def load_cognitive_capsule(self) -> Dict[str, Any]:
        """Hydrates the brain with the vibe of the last session."""
        try:
            capsule_path = "data/cognitive_capsule.json"
            if os.path.exists(capsule_path):
                # Ensure file is not empty
                if os.path.getsize(capsule_path) == 0:
                    logger.info("SessionRestorer: Cognitive capsule is empty. Starting fresh.")
                    return {}
                    
                with open(capsule_path, "r") as f:
                    try:
                        data = json.load(f)
                        return data.get("payload", {})
                    except json.JSONDecodeError:
                        logger.warning("SessionRestorer: Cognitive capsule corrupted. Clean slate initiated.")
                        return {}
        except Exception as e:
            logger.debug(f"SessionRestorer: Adaptive recovery for capsule: {e}")
        return {}
    def restore_peak_equity(self, db_path: str, drawdown_ladder: Any) -> float:
        """
        Reads the last known peak_equity from the DB and restores it into
        the DrawdownLadder so the high-water mark survives restarts.
        """
        try:
            conn = sqlite3.connect(db_path, timeout=60.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key='peak_equity'")
            row = cursor.fetchone()
            conn.close()
            if row:
                peak = float(row[0])
                drawdown_ladder.peak_equity = peak
                logger.info(f"SessionRestorer: Restored peak_equity=${peak:.2f} into DrawdownLadder.")
                return peak
        except Exception as e:
            logger.warning(f"SessionRestorer: Could not restore peak_equity: {e}")
        return drawdown_ladder.peak_equity

    async def reconcile_with_broker(self, ib: Any, db_conn: sqlite3.Connection) -> list[Any]:
        """
        Sovereign Reconciliation (Samvid v1.0-beta-beta): The 'Adoption' Protocol.
        Synchronizes broker positions with the database and managed tasks.
        Returns a list of Position objects to be injected into the Brain.
        """
        logger.info("🛡  Reconciler: Probing broker for state discrepancies...")
        adopted_positions = []
        
        try:
            # 1. Fetch current Broker Positions
            ib_pos = ib.positions()
            broker_map = {p.contract.symbol: p for p in ib_pos}
            
            # 2. Fetch Active Database Trades
            db_conn.row_factory = sqlite3.Row # Ensure safe dictionary-style access
            cursor = db_conn.cursor()
            cursor.execute("SELECT id, instrument, direction, shares_remaining, stop_price, target_price FROM trades WHERE status = 'OPEN'")
            db_trades = cursor.fetchall()
            db_map = {t['instrument']: t for t in db_trades}
            
            # 3. Handle ORPHANS (In Broker, but not managed in DB)
            from system_types import Position
            
            for symbol, p in broker_map.items():
                broker_qty = abs(p.position)
                if symbol not in db_map:
                    logger.warning(f"🧟 Reconciler: ORPHAN DETECTED [{symbol} | {broker_qty}]. Initiating Adoption Protocol.")
                    
                    # GAP-61 FIX: Get actual market price if avgCost is 0
                    price = p.avgCost
                    if price <= 0:
                        try:
                            # Attempt to get last tick from IB cache
                            ticker = ib.ticker(p.contract)
                            price = ticker.last or ticker.close or ticker.marketPrice() or 0.0
                            logger.info(f"Reconciler: avgCost was 0 for {symbol}. Fetched marketPrice: ${price:.2f}")
                        except Exception:
                            price = 0.0
                    
                    if price <= 0:
                        logger.error(f"Zombie Trade Risk: Could not resolve valid price for {symbol}. DEFERRING adoption.")
                        continue
                        
                    direction = "LONG" if p.position > 0 else "SHORT"
                    
                    # GAP-107 FIX: Dynamic Stop/Target based on ATR or 2.5x spread (fallback to 2.5%)
                    # Previously was hardcoded 1.5% which was too tight for adoption.
                    stop_dist = price * 0.025 
                    target_dist = price * 0.05
                    
                    # Create the Adoption Record
                    adopted = Position(
                        symbol=symbol,
                        qty=broker_qty,
                        entry_price=price,
                        entry_time=datetime.now(timezone.utc),
                        pattern="ADOPTED_ORPHAN",
                        status="OPEN",
                        stop_loss=price - stop_dist if direction == "LONG" else price + stop_dist,
                        take_profit=price + target_dist if direction == "LONG" else price - target_dist,
                        shares_remaining=broker_qty,
                        meta={"adoption_ts": datetime.now(timezone.utc).isoformat()}
                    )
                    
                    # Persist Adoption to DB
                    cursor.execute(
                        "INSERT INTO trades (instrument, direction, quantity, entry_price, status, stop_price, target_price, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (symbol, direction, broker_qty, price, "OPEN", adopted.stop_loss, adopted.take_profit, "Sovereign Adoption Protocol v1.0-beta")
                    )
                    adopted.db_id = cursor.lastrowid
                    adopted_positions.append(adopted)
                    logger.info(f"✓ Reconciler: Adopted {symbol} (Target: {adopted.take_profit:.2f}, Stop: {adopted.stop_loss:.2f})")
                else:
                    # GAP-106 FIX: Quantity Reconciliation for managed trades
                    db_trade = db_map[symbol]
                    db_qty = db_trade['shares_remaining']
                    if abs(db_qty - broker_qty) > 0.001: # Use epsilon for float safety
                        logger.warning(f"⚖️ Reconciler: QUANTITY MISMATCH for {symbol}. DB: {db_qty} | Broker: {broker_qty}. Synchronizing to Broker.")
                        cursor.execute(
                            "UPDATE trades SET shares_remaining = ?, quantity = ?, notes = notes || ? WHERE id = ?",
                            (broker_qty, broker_qty, f" | Qty Recon: {db_qty}->{broker_qty}", db_trade['id'])
                        )

            # 4. Handle GHOSTS (In DB but no longer in Broker)
            for symbol, t in db_map.items():
                if symbol not in broker_map:
                    # GAP-105 FIX: Drift Veto (Verify if the DB record was created very recently)
                    # If it was created < 60s ago, it might be a race condition where IB hasn't updated yet.
                    # We only close if it's "Mature" (> 60s old).
                    try:
                        cursor.execute("SELECT created_at FROM trades WHERE id = ?", (t['id'],))
                        created_str = cursor.fetchone()[0]
                        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if (datetime.now(timezone.utc) - created_dt).total_seconds() < 60:
                            logger.info(f"⏳ Reconciler: Skipping Ghost Veto for {symbol} (Age < 60s, potential race).")
                            continue
                    except Exception: pass

                    logger.info(f"👻 Reconciler: GHOST DETECTED [{symbol}]. Closing record (Terminal discrepancy).")
                    cursor.execute(
                        "UPDATE trades SET status = 'CLOSED', exit_reason = 'GHOST_SYNCHRONIZED', exit_time = ? WHERE id = ?",
                        (datetime.now(timezone.utc).isoformat(), t['id'])
                    )

            db_conn.commit()
            return adopted_positions

        except Exception as e:
            logger.error(f"Reconciler: Recovery Loop Failed: {e}")
            return []
