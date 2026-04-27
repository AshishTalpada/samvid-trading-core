import asyncio
import logging
import socket
import time
from typing import Any

from mind_bridge import MindBridge

logger = logging.getLogger(__name__)


class MindGhost:
    """
    Agent J: The Ghost Monitor (SETO V7.0).
    Focuses on 'Sub-Second UI/API Auditing' and 'Ghost State Monitoring'.
    Inspired by Claude-Code's tmuxSocket.ts and terminalPanel.ts.
    Detects when a service (like IBKR) is 'Hanging' but hasn't 'Crashed'.
    """

    def __init__(self, bridge: MindBridge) -> None:
        self.bridge = bridge
        self.is_running = False
        self.latency_threshold_ms = 500  # 500ms threshold for 'Hanging'
        self.last_api_heartbeat = time.time()
        self.startup_time = time.time()  # For grace period (SETO V8.0 Extended)
        self.ghost_mirror: dict[str, Any] = {}  # Internal 'Mirror' of service states

        # --- SETO V8.0 PILLAR 4: EXPONENTIAL BACKOFF (Agent J) ---
        self.retry_counts: dict[str, int] = {}
        self.backoff_base = 2.0
        # Track when next probe is allowed per service (exponential backoff)
        self._probe_next_allowed: dict[str, float] = {}
        self._probe_backoff_sec: dict[str, float] = {"IBKR": 30.0, "MT5": 60.0}

    async def start(self) -> None:
        """Launch the Ghost Monitor."""
        self.is_running = True
        logger.info("MindGhost (Agent J): Ghost Monitoring active (SETO V7.0).")
        task = asyncio.create_task(self._ghost_audit_loop())
        
        # GAP-167: Supervisor Monitoring (Heartbeat)
        def _ghost_dead_callback(t: asyncio.Task) -> None:
            if self.is_running: # If it wasn't a clean stop
                try:
                    if t.cancelled():
                        # Just a shutdown, no need to log as critical
                        return
                    
                    err = t.exception()
                    msg = f"🚨 <b>CRITICAL</b>: MindGhost (Agent J) has CRASHED! {err}"
                except (asyncio.CancelledError, Exception) as e:
                    # Catch CancelledError explicitly if raised by exception()
                    if isinstance(e, asyncio.CancelledError):
                        return
                    msg = "🚨 <b>CRITICAL</b>: MindGhost (Agent J) has STOPPED UNEXPECTEDLY!"
                
                logger.critical(msg)
                asyncio.create_task(self.bridge.broadcast(
                    "ghost", 
                    msg, 
                    {"alert": "TELEGRAM", "urgency": "FATAL"}
                ))

        task.add_done_callback(_ghost_dead_callback)

    async def _ghost_audit_loop(self) -> None:
        """The core audit loop that runs at sub-second frequency."""
        from time_sync import TimeSync
        while self.is_running:
            try:
                current_time = TimeSync.now().timestamp()

                # SETO V8.0: 120-second Grace Period on startup (Allows for slow IBKR handshakes)
                if current_time - self.startup_time < 120:
                    await asyncio.sleep(1.0)
                    continue

                # 1. Handshake Verification (SETO V9.99 Bus-Driven)
                # If we're still waiting for a handshake, check if the system heartbeats are active
                if self.last_api_heartbeat <= self.startup_time:
                    # If we catch a bus event or a mirror update, sync the heartbeat
                    if self.ghost_mirror.get("IBKR") == "connected" or self.ghost_mirror.get("MT5") == "connected":
                        self.last_api_heartbeat = current_time
                        logger.info("MindGhost: Handshake confirmed via Global Matrix. Audit mode ENGAGED.")

                # 2. API Heartbeat Audit (SETO V9.99 Adaptive Patience)
                if self.last_api_heartbeat > self.startup_time:
                    # GAP-38 FIX: Increased timeout to 60s (from 30s) to allow for heavy vetting cycles
                    if current_time - self.last_api_heartbeat > 60.0:
                        logger.error(f"MindGhost: API HEARTBEAT LOST! (Last: {int(current_time - self.last_api_heartbeat)}s ago). Service may be hanging.")
                        await self._trigger_ghost_reset("IBKR")
                else:
                    # We haven't connected yet — just keep waiting quietly (Quieted to 15s reports)
                    if int(current_time) % 15 == 0:
                        logger.debug("MindGhost: Waiting for Sovereign Matrix Handshake...")

                # 2. Latency Spikes Audit
                # If Mind F (Executioner) reports high latency, we take action

                # 3. ACTIVE SOCKET PROBE with exponential backoff (IBKR ONLY)
                if int(current_time) % 30 == 0:
                    # GAP-264 FIX: Tick-gate to prevent double-probing within the same second
                    if getattr(self, "_last_probe_tick", 0) != int(current_time):
                        self._last_probe_tick = int(current_time)
                        
                        for service, port in [("IBKR", 7497)]:
                            next_ok = self._probe_next_allowed.get(service, 0)
                            if current_time < next_ok:
                                continue  # still in backoff window
                            
                            # GAP-264 FIX: Offload blocking socket I/O to thread
                            if not await asyncio.to_thread(self._probe_port, port):
                                fail_count = self.ghost_mirror.get(f"{service}_probe_fail", 0) + 1
                                self.ghost_mirror[f"{service}_probe_fail"] = fail_count
                                # Only log on first failure and each doubled interval
                                backoff = min(self._probe_backoff_sec.get(service, 60.0) * (2 ** (fail_count - 1)), 480.0)
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
                                self._probe_backoff_sec[service] = 30.0 if service == "IBKR" else 60.0
                                self._probe_next_allowed[service] = 0

                await asyncio.sleep(0.5)  # Sub-second frequency
            except Exception as e:
                logger.error(f"MindGhost Audit Error: {e}")
                await asyncio.sleep(1)

    async def _trigger_ghost_reset(self, service_name: str) -> None:
        """
        Triggers an autonomous service reset with Pillar 4 Exponential Backoff.
        This is a 'Ghost Reset' because it happens before the system actually crashes.
        """
        retry_count = self.retry_counts.get(service_name, 0)
        backoff_delay = self.backoff_base**retry_count

        logger.warning(
            f"MindGhost: Initiating GHOST RESET sequence for {service_name} (Attempt {retry_count + 1}, Delay {backoff_delay:.1f}s)..."
        )
        # Pillar 4: Signal the Matrix + User via Bridge
        await self.bridge.broadcast(
            "ghost",
            f"☣️ EMERGENCY RESET WARNING: {service_name} heartbeat failure. Rebooting in 5s unless system scent returns.",
            {"alert": "TELEGRAM", "urgency": "CRITICAL"}
        )

        await asyncio.sleep(backoff_delay)

        # FINAL PATIENCE GAP: Reduced for HFT (GAP-38)
        await asyncio.sleep(5.0)

        # Call the reboot_service tool on Agent I via the Bridge
        result = await self.bridge.call_tool(
            "reboot_service", service_name=f"RESTART_{service_name}"
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
                    f"MindGhost: Ghost Reset of {service_name} FAILED! Max retries exceeded. Escalating."
                )
                await self.bridge.broadcast(
                    "ghost",
                    f"ESCALATION: Ghost Reset of {service_name} failed. Emergency shutdown advised.",
                )
            else:
                logger.error(
                    f"MindGhost: Ghost Reset of {service_name} FAILED! (Backoff increasing to {self.backoff_base ** (retry_count + 1):.1f}s)"
                )

    async def update_heartbeat(self, service: str) -> None:
        """Called by Executioner (Mind F) or Brain to confirm system/API is alive."""
        # Any valid heartbeat from core services keeps the Ghost satisfied
        if service in ("IBKR", "MT5", "ENGINE", "CORE"):
            from time_sync import TimeSync
            self.last_api_heartbeat = TimeSync.now().timestamp()
            # If we were in handshake mode, this confirms success
            if self.last_api_heartbeat > self.startup_time:
                self.ghost_mirror[service] = "connected"

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
