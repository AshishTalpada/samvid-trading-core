import asyncio
import json
import logging
import os
import socket
import time
import uuid
from pathlib import Path
from typing import Any, Dict

from mind_bridge import MindBridge

logger = logging.getLogger(__name__)


class MindGhost:
    """
    Agent J: The Ghost Monitor.
    Focuses on 'Sub-Second UI/API Auditing' and 'Ghost State Monitoring'.
    Inspired by Claude-Code's tmuxSocket.ts and terminalPanel.ts.
    Detects when a service (like IBKR) is 'Hanging' but hasn't 'Crashed'.
    """

    def __init__(self, bridge: MindBridge) -> None:
        self.bridge = bridge
        self.is_running = False
        self._stand_down = False
        self.latency_threshold_ms = 500  # 500ms threshold for 'Hanging'
        self.last_api_heartbeat = time.time()
        self.startup_time = time.time()  # For grace period
        self.ghost_mirror: dict[str, Any] = {}  # Internal 'Mirror' of service states

        self.retry_counts: dict[str, int] = {}
        self.backoff_base = 2.0
        # Track when next probe is allowed per service (exponential backoff)
        self._probe_next_allowed: dict[str, float] = {}
        self._probe_backoff_sec: dict[str, float] = {"IBKR": 30.0, "MT5": 60.0}
        self._next_api_loss_alert = 0.0
        self._heartbeat_registry_path = Path("data/task_heartbeats.json")
        self._heartbeat_registry_max_age = 90.0
        self._registry_recovery_logged = False
        self._next_reset_suppressed_log = 0.0

        # FIX: Store task references to allow clean cancellation on shutdown.
        # Dropping these references causes 'Task was destroyed but it is pending!'
        self._audit_task: asyncio.Task | None = None
        self._shutdown_listener_task: asyncio.Task | None = None

    async def stop(self) -> None:
        """Cleanly cancel all background tasks to prevent asyncio leak on shutdown."""
        self.is_running = False
        self._stand_down = True
        for t in (self._audit_task, self._shutdown_listener_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass
        logger.info("MindGhost (Agent J): Stopped cleanly.")

    async def start(self) -> None:
        """Launch the Ghost Monitor."""
        self.is_running = True
        logger.info("MindGhost (Agent J): Ghost Monitoring active.")

        # Start audit loop — store reference to allow clean cancellation
        self._audit_task = asyncio.create_task(self._ghost_audit_loop())

        # FIX: Store shutdown listener reference to prevent 'Task destroyed' error on restart.
        # Previously created with create_task() and reference dropped immediately.
        if self.bridge.bus:
            self._shutdown_listener_task = asyncio.create_task(self._shutdown_listener())

        def _ghost_dead_callback(t: asyncio.Task) -> None:
            if self.is_running:  # If it wasn't a clean stop
                try:
                    if t.cancelled():
                        return
                    err = t.exception()
                    msg = f" <b>CRITICAL</b>: MindGhost (Agent J) has CRASHED! {err}"
                except (asyncio.CancelledError, Exception) as e:
                    if isinstance(e, asyncio.CancelledError):
                        return
                    msg = " <b>CRITICAL</b>: MindGhost (Agent J) has STOPPED UNEXPECTEDLY!"
                logger.critical(msg)
                asyncio.create_task(
                    self.bridge.broadcast("ghost", msg, {"alert": "TELEGRAM", "urgency": "FATAL"})
                )

        self._audit_task.add_done_callback(_ghost_dead_callback)

    async def _shutdown_listener(self) -> None:
        """Listens for the system shutdown signal to stand down."""
        if not self.bridge.bus:
            return
        q = self.bridge.bus.subscribe("system.status")
        while self.is_running:
            try:
                msg = await q.get()
                if msg.get("state") == "SHUTDOWN":
                    logger.info("MindGhost: Shutdown signal received. Standing down.")
                    self._stand_down = True
            except Exception:
                await asyncio.sleep(1)

    async def _ghost_audit_loop(self) -> None:
        """The core audit loop that runs at sub-second frequency."""
        from time_sync import TimeSync

        while self.is_running:
            try:
                if self._stand_down:
                    await asyncio.sleep(1)
                    continue
                current_time = TimeSync.now().timestamp()
                if current_time - self.startup_time < 120:
                    await asyncio.sleep(1.0)
                    continue
                if self.last_api_heartbeat <= self.startup_time:
                    if (
                        self.ghost_mirror.get("IBKR") == "connected"
                        or self.ghost_mirror.get("MT5") == "connected"
                    ):
                        self.last_api_heartbeat = current_time
                        logger.info(
                            "MindGhost: Handshake confirmed via Global Matrix. Audit mode ENGAGED."
                        )
                self._refresh_from_task_registry(current_time)
                if self.last_api_heartbeat > self.startup_time:
                    if current_time - self.last_api_heartbeat > 60.0:
                        if current_time >= self._next_api_loss_alert:
                            logger.error(
                                f"MindGhost: API HEARTBEAT LOST! (Last: "
                                f"{int(current_time - self.last_api_heartbeat)}s ago). "
                                "Service may be hanging."
                            )
                            await self._trigger_ghost_reset("IBKR")
                            self._next_api_loss_alert = current_time + 60.0
                else:
                    if int(current_time) % 15 == 0:
                        logger.debug("MindGhost: Waiting for Sovereign Matrix Handshake...")
                if int(current_time) % 30 == 0:
                    if getattr(self, "_last_probe_tick", 0) != int(current_time):
                        self._last_probe_tick = int(current_time)
                        from vault import Vault

                        ibkr_port = int(Vault.get("IBKR_PORT", "7497"))
                        for service, port in [("IBKR", ibkr_port)]:
                            next_ok = self._probe_next_allowed.get(service, 0)
                            if current_time < next_ok:
                                continue
                            if not await asyncio.to_thread(self._probe_port, port):
                                fail_count = self.ghost_mirror.get(f"{service}_probe_fail", 0) + 1
                                self.ghost_mirror[f"{service}_probe_fail"] = fail_count
                                backoff = min(
                                    self._probe_backoff_sec.get(service, 60.0)
                                    * (2 ** (fail_count - 1)),
                                    480.0,
                                )
                                self._probe_backoff_sec[service] = backoff
                                self._probe_next_allowed[service] = current_time + backoff
                                logger.warning(
                                    f"MindGhost: Socket Probe FAILED for {service}:{port} "
                                    f"(fail #{fail_count}, next probe in {backoff:.0f}s)"
                                )
                                if fail_count >= 2:
                                    await self._trigger_ghost_reset(service)
                            else:
                                if self.ghost_mirror.get(f"{service}_probe_fail", 0) > 0:
                                    logger.info(f"MindGhost: {service} probe RECOVERED.")
                                self.ghost_mirror[f"{service}_probe_fail"] = 0
                                self._probe_backoff_sec[service] = (
                                    30.0 if service == "IBKR" else 60.0
                                )
                                self._probe_next_allowed[service] = 0

                await asyncio.sleep(0.5)  # Sub-second frequency
            except Exception as e:
                logger.error(f"MindGhost Audit Error: {e}")
                await asyncio.sleep(1)

    async def _trigger_ghost_reset(self, service_name: str) -> None:
        """Triggers an autonomous service reset."""
        from vault import Vault

        auto_restart = Vault.get("IBKR_AUTO_RESTART", "0").strip() == "1"
        if service_name == "IBKR" and not auto_restart:
            now = time.monotonic()
            if now >= self._next_reset_suppressed_log:
                logger.warning(
                    "MindGhost: IBKR reset suppressed because IBKR_AUTO_RESTART is disabled."
                )
                self._next_reset_suppressed_log = now + 300.0
            return

        retry_count = self.retry_counts.get(service_name, 0)
        backoff_delay = self.backoff_base**retry_count

        logger.warning(
            f"MindGhost: Initiating GHOST RESET sequence for {service_name} "
            f"(Attempt {retry_count + 1}, Delay {backoff_delay:.1f}s)..."
        )
        await self.bridge.broadcast(
            "ghost",
            f" EMERGENCY RESET WARNING: {service_name} heartbeat failure. "
            "Rebooting in 5s unless system scent returns.",
            {"alert": "TELEGRAM", "urgency": "CRITICAL"},
        )

        await asyncio.sleep(backoff_delay)

        # FINAL PATIENCE GAP: Reduced for HFT
        await asyncio.sleep(5.0)

        # Call the reboot_service tool on Agent I via the Bridge
        result = await self.bridge.call_tool(
            "reboot_service",
            service_name=f"RESTART_{service_name}",
            justification=(
                f"GHOST_RESET: Heartbeat lost for {service_name} (Attempt {retry_count + 1})"
            ),
        )

        if result.get("status") == "OK":
            logger.info(f"MindGhost: Ghost Reset of {service_name} SUCCESSFUL.")
            from time_sync import TimeSync

            self.last_api_heartbeat = TimeSync.now().timestamp()
            self.retry_counts[service_name] = 0  # Reset on success
        else:
            self.retry_counts[service_name] = retry_count + 1
            if self.retry_counts[service_name] > 5:
                logger.error(
                    f"MindGhost: Ghost Reset of {service_name} FAILED! "
                    "Max retries exceeded. Escalating."
                )
                await self.bridge.broadcast(
                    "ghost",
                    f"ESCALATION: Ghost Reset of {service_name} failed. "
                    "Emergency shutdown advised.",
                )
            else:
                logger.error(
                    f"MindGhost: Ghost Reset of {service_name} FAILED! "
                    f"(Backoff increasing to {self.backoff_base ** (retry_count + 1):.1f}s)"
                )

    async def update_heartbeat(self, service: str) -> None:
        """Called by Executioner (Mind F) or Brain to confirm system/API is alive."""
        # Any valid heartbeat from core services keeps the Ghost satisfied
        if service in ("IBKR", "MT5", "ENGINE", "CORE"):
            from time_sync import TimeSync

            self.last_api_heartbeat = TimeSync.now().timestamp()
            self._next_api_loss_alert = 0.0
            self._registry_recovery_logged = False
            # If we were in handshake mode, this confirms success
            if self.last_api_heartbeat > self.startup_time:
                self.ghost_mirror[service] = "connected"

    def _refresh_from_task_registry(self, current_time: float) -> None:
        """Accept fresh DMS task heartbeats as proof that the engine is alive."""
        try:
            if not self._heartbeat_registry_path.exists():
                return
            with self._heartbeat_registry_path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return
            registry_pid = payload.get("pid")
            if registry_pid and int(registry_pid) != os.getpid():
                return
            heartbeats = payload.get("heartbeats") or {}
            if not isinstance(heartbeats, dict) or not heartbeats:
                return
            latest = max(float(ts) for ts in heartbeats.values())
            age = current_time - latest
            if age <= self._heartbeat_registry_max_age:
                if latest > self.last_api_heartbeat:
                    self.last_api_heartbeat = latest
                    self._next_api_loss_alert = 0.0
                    self.ghost_mirror["ENGINE"] = "connected"
                    if not self._registry_recovery_logged:
                        logger.info(
                            "MindGhost: Engine heartbeat confirmed via DMS registry "
                            f"({age:.1f}s old)."
                        )
                        self._registry_recovery_logged = True
            elif self._registry_recovery_logged:
                self._registry_recovery_logged = False
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.debug(f"MindGhost: DMS heartbeat registry read skipped: {exc}")

    def _probe_port(self, port: int) -> bool:
        """Low-level TCP handshake to detect hung local services."""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2.0):
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False
        except Exception as e:
            logger.debug(f"MindGhost: Probe error on port {port}: {e}")
            return False


# ── LOCAL-ONLY MODULE CONSTANTS ─────────────────────────────────────────

# ── LOCAL-ONLY SOVEREIGN EXTENSIONS ─────────────────────────────────────


class GhostExecutionEnvironment:
    """
    Deep Dive: The Ghost Protocol.
    A completely isolated shadow-execution environment. When Sovereign comes up with
    a highly experimental trading strategy (low confidence), it routes it to the Ghost Environment
    instead of the real Broker Arbitrator. The Ghost environment simulates slippage, liquidity
    impact, and queue positions to track how the trade *would* have performed.
    """

    def __init__(self, bridge: Any = None, **kwargs):
        self.bridge = bridge
        self.ghost_ledger: Dict[str, dict] = {}
        self.active_ghost_positions: Dict[str, dict] = {}
        self.heartbeats: Dict[str, float] = {}
        # Simulate institutional commission: $0.005 per share, min $1.00
        self.commission_per_share = 0.005
        self.min_commission = 1.00

        if self.bridge:
            self.bridge.register_tool("route_shadow_trade", self.route_shadow_trade)
            self.bridge.register_tool("get_ghost_status", self._tool_get_ghost_status)
            self.bridge.register_tool("close_shadow_trade", self.close_shadow_trade)

    async def update_heartbeat(self, component: str):
        """
        Records a heartbeat for a specific ghost component.
        """
        self.heartbeats[component] = time.time()
        logger.debug(f"[GHOST] Heartbeat updated for {component}")

    async def start(self):
        """Launch Agent J (Shadow Environment)."""
        logger.info("[GHOST] Ghost Protocol ENGAGED. Shadow execution environment online.")

    def _calculate_commission(self, size: float) -> float:
        return max(self.min_commission, size * self.commission_per_share)

    def route_shadow_trade(
        self, symbol: str, action: str, price: float, size: float, logic_signature: str
    ) -> str:
        """
        Ingests a trade intent and immediately fills it in the local shadow memory.
        """
        trade_id = f"GHOST-{uuid.uuid4().hex[:8]}"

        # Simulate slippage based on size (simplified linear impact)
        simulated_slippage = (size / 100.0) * 0.0001
        fill_price = (
            price * (1.0 + simulated_slippage)
            if action == "BUY"
            else price * (1.0 - simulated_slippage)
        )

        commission = self._calculate_commission(size)

        from time_sync import TimeSync

        position = {
            "symbol": symbol,
            "action": action,
            "fill_price": fill_price,
            "size": size,
            "logic_signature": logic_signature,
            "timestamp": TimeSync.now().timestamp(),
            "unrealized_pnl": -commission,  # Start down by commission
            "entry_commission": commission,
        }

        self.active_ghost_positions[trade_id] = position
        logger.info(
            f"[GHOST] Shadow trade {trade_id} executed on {symbol}. "
            f"Fill: {fill_price:.2f} (Comm: ${commission:.2f})"
        )
        return trade_id

    def update_ghost_pnl(self, current_market_prices: Dict[str, float]):
        """
        Continuously mark-to-market the active shadow positions.
        """
        for trade_id, pos in self.active_ghost_positions.items():
            sym = pos["symbol"]
            if sym in current_market_prices:
                current_price = current_market_prices[sym]
                if pos["action"] == "BUY":
                    pnl = (current_price - pos["fill_price"]) * pos["size"]
                else:
                    pnl = (pos["fill_price"] - current_price) * pos["size"]

                # Account for entry commission
                pos["unrealized_pnl"] = pnl - pos["entry_commission"]

    def close_shadow_trade(self, trade_id: str, current_price: float) -> float:
        """Closes a ghost position and permanently logs its realized PnL."""
        if trade_id not in self.active_ghost_positions:
            return 0.0

        pos = self.active_ghost_positions.pop(trade_id)

        # Simulate closing slippage
        simulated_slippage = (pos["size"] / 100.0) * 0.0001
        close_price = (
            current_price * (1.0 - simulated_slippage)
            if pos["action"] == "BUY"
            else current_price * (1.0 + simulated_slippage)
        )

        exit_commission = self._calculate_commission(pos["size"])

        if pos["action"] == "BUY":
            gross_pnl = (close_price - pos["fill_price"]) * pos["size"]
        else:
            gross_pnl = (pos["fill_price"] - close_price) * pos["size"]

        realized_pnl = gross_pnl - pos["entry_commission"] - exit_commission

        pos["realized_pnl"] = realized_pnl
        pos["exit_commission"] = exit_commission
        pos["close_time"] = time.time()

        self.ghost_ledger[trade_id] = pos
        logger.info(f"[GHOST] Closed {trade_id}. Realized Net PnL: ${realized_pnl:.2f}")

        # Prune ledger in batches when limit is reached
        if len(self.ghost_ledger) > 1000:
            # Remove oldest 100 entries
            ids_to_prune = list(self.ghost_ledger.keys())[:100]
            for pid in ids_to_prune:
                self.ghost_ledger.pop(pid, None)
            logger.debug(
                f"[GHOST] Pruned 100 entries from ledger. Current size: {len(self.ghost_ledger)}"
            )

        return realized_pnl

    async def _tool_get_ghost_status(self) -> Dict[str, Any]:
        """Provides the Brain with the current state of shadow execution."""
        total_unrealized = sum(p["unrealized_pnl"] for p in self.active_ghost_positions.values())
        return {
            "active_count": len(self.active_ghost_positions),
            "unrealized_pnl": total_unrealized,
            "positions": self.active_ghost_positions,
            "status": "OPERATIONAL",
        }


class GhostInfrastructureMonitor:
    """
    Agent J Extension: The Infrastructure Monitor.
    Detects when a service (like IBKR) is 'Hanging' but hasn't 'Crashed'.
    """

    def __init__(self, bridge: Any) -> None:
        self.bridge = bridge
        self.is_running = False
        self.last_api_heartbeat = time.time()
        self.ghost_mirror: dict[str, Any] = {}
        self.retry_counts: dict[str, int] = {}
        self._probe_next_allowed: dict[str, float] = {}

    async def start(self) -> None:
        self.is_running = True
        logger.info("[GHOST] Infrastructure Monitor active.")
        asyncio.create_task(self._audit_loop())

    async def _audit_loop(self) -> None:
        while self.is_running:
            try:
                # Active socket probe for IBKR (7497)
                if not await asyncio.to_thread(self._probe_port, 7497):
                    logger.warning("[GHOST] IBKR Socket Probe FAILED. Service may be hanging.")
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"[GHOST] Audit Error: {e}")
                await asyncio.sleep(5)

    def _probe_port(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2.0):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False
        except Exception as e:
            logger.debug(f"[GHOST] Probe error on port {port}: {e}")
            return False
