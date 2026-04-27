# pyre-ignore-all-errors[21]
"""
src/dms.py - Dead Man Switch Monitor (v1.0-beta-beta-beta)

Monitors system health and flattens all positions if the trading system
goes unresponsive. Uses Telegram for alerts and IB Gateway + MT5 for
emergency position flattening.

Implements:
- GAP-06: Emergency flatten logic via IBKR and MT5
- v1.0-beta-beta DMS: Agent C alive check → 5-min grace → flatten
- Heartbeat monitoring with 30s check intervals
- Hourly status reports via Telegram
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import aiohttp
import MetaTrader5 as mt5  # type: ignore

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus

from vault import Vault  # pyre-ignore[21]

logger = logging.getLogger(__name__)


class DMSMonitor:
    """
    Dead Man Switch — if the primary trading system goes offline,
    this monitor detects the timeout and flattens all positions.
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        timeout: int = 300,
        ibkr_client=None,
        mt5_client=None,
        ibkr_port: int = 7497,
        bus: Optional["SharedIntelligenceBus"] = None,
    ) -> None:
        self.bus = bus
        # Samvid v1.0-beta-beta-beta Support: Secure fallback to Vault
        if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
            bot_token = Vault.get("TELEGRAM_BOT_TOKEN", "")
        if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
            chat_id = Vault.get("TELEGRAM_CHAT_ID", "")

        self.bot_token = bot_token
        self.chat_id = chat_id
        self.ibkr_port = ibkr_port  # Samvid v1.0-beta-beta-beta Port Injection
        self.timeout = timeout  # Configurable; default 300s from constructor
        self.max_retries = 2
        self.retry_count = 0

        # GAP-84: Modular Heartbeat Registry
        self.agent_heartbeats: dict[str, datetime] = {
            "BRAIN_PRIMARY": datetime.now(timezone.utc),
        }
        self.critical_agents = ["BRAIN_PRIMARY", "AGENT_A", "AGENT_C", "COORDINATOR"]

        self.last_status_ok = datetime.now(timezone.utc)
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self.running = False
        self.alert_sent = False
        self.flatten_executed = False
        self.session: aiohttp.ClientSession | None = None

        # Broker connections for emergency flatten
        self.ibkr_client = ibkr_client
        self.mt5_client = mt5_client

        # v1.0-beta-beta: Grace period before flatten (Agent C alive check)
        self.grace_period = 15  # 15 seconds (down from 30s) (GAP-85)
        self.timeout_detected_at: datetime | None = None

    async def __aenter__(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        session = self.session
        if session:
            await session.close()
        return False

    async def _send_telegram_message(self, message: str) -> bool:
        """Send message via Telegram API."""
        session = self.session
        if not session:
            from session_manager import SovereignSession
            session = await SovereignSession.get_session()
            self.session = session

        if not self.bot_token:
            logger.debug("Telegram not configured — skipping message")
            return False

        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}

        try:
            # Samvid v1.0-beta-beta-beta: Telegram Timeout Hardening (30s)
            timeout = aiohttp.ClientTimeout(total=30.0)
            async with session.post(url, json=payload, timeout=timeout) as response:
                if response.status == 200:
                    logger.info(f"Telegram message sent: {message[:50]}...")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Telegram failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Exception sending Telegram message: {e}")
            return False
        # unreachable path — all branches above return; explicit for clarity
        return False  # noqa: F811

    def record_heartbeat(self, agent_id: str = "BRAIN_PRIMARY") -> None:
        """Record a heartbeat from a specific agent."""
        self.agent_heartbeats[agent_id] = datetime.now(timezone.utc)
        self.alert_sent = False
        self.flatten_executed = False
        self.timeout_detected_at = None

    async def check_timeout(self) -> bool:
        """Check if any critical agent heartbeat timeout exceeded."""
        current_time = datetime.now(timezone.utc)
        stale_agents = []

        for agent in self.critical_agents:
            last_hb = self.agent_heartbeats.get(agent)
            if not last_hb:
                # If a critical agent hasn't reported even once yet, give it 5 min warmup
                uptime = (current_time - self.last_status_ok).total_seconds()
                if uptime > 300:
                    stale_agents.append(f"{agent} (NO START)")
                continue

            time_since_hb = (current_time - last_hb).total_seconds()
            if time_since_hb > self.timeout:
                stale_agents.append(f"{agent} ({int(time_since_hb)}s)")

        if stale_agents:
            # v1.0-beta-beta: Differentiate between connection blips and actual crashes
            self.retry_count += 1
            if self.retry_count < self.max_retries:
                logger.warning(f"DMS: Ghost drift detected in {stale_agents} ({self.retry_count}/{self.max_retries}).")
                return False

            # Timeout detected
            timeout_at = self.timeout_detected_at
            if timeout_at is None:
                timeout_at = current_time
                self.timeout_detected_at = timeout_at
                logger.warning(f"CRITICAL: Ghost drift detected! Stale Agents: {stale_agents}")

            # Send alert (once)
            if not self.alert_sent:
                await self.send_emergency_alert(stale_agents)
                self.alert_sent = True

            # v1.0-beta-beta: Wait grace period, then execute flatten
            grace_elapsed = (current_time - timeout_at).total_seconds()
            if grace_elapsed >= self.grace_period and not self.flatten_executed:
                logger.critical(f"DMS: Panic threshold reached for {stale_agents} — executing emergency flatten!")
                await self.execute_emergency_flatten()
                self.flatten_executed = True

            return True

        # Heartbeat received within timeout
        self.retry_count = 0
        return False

    async def send_emergency_alert(self, stale_agents: list[str]) -> None:
        """Send emergency alert via Telegram."""
        current_time = datetime.now(timezone.utc)

        message = (
            "🚨 <b>[EMERGENCY] GHOST DRIFT DETECTED!</b> 🚨\n\n"
            f"🕒 <b>Alert Time:</b> {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚠ <b>Stale Agents:</b> {', '.join(stale_agents)}\n"
            f"⚙ <b>Timeout Threshold:</b> {self.timeout} seconds\n"
            f"🛡 <b>Grace Period:</b> {self.grace_period}s before flatten\n\n"
            "<b>Mind Ghost Logic activated!</b>\n"
            f"Positions will be flattened in {self.grace_period}s if agents do not recover."
        )

        await self._send_telegram_message(message)
        logger.critical(f"Emergency alert sent for {stale_agents}!")

    async def execute_emergency_flatten(self, _retries: int = 3) -> list[str]:
        """
        FLATTEN ALL POSITIONS via IBKR and MT5.
        This is the actual Dead Man Switch action.
        """
        # GAP-89/91: Global Concurrency Lock (Atomic O_EXCL implementation)
        import os
        import socket
        import time

        from data_pipeline import DataPipeline
        lock_file = DataPipeline.DMS_LOCK_FILE

        # Proactive directory creation (GAP-91)
        try:
            os.makedirs(os.path.dirname(lock_file), exist_ok=True)
        except Exception as e:
            logger.error(f"DMS: Directory creation failed: {e}")

        # Atomic lock creation (GAP-89)
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as f:
                f.write(f"LATENCY_CRITICAL node={socket.gethostname()} ts={datetime.now(timezone.utc).isoformat()}")
        except FileExistsError:
            # Check if the lock is stale (> 30 mins)
            if (time.time() - os.path.getmtime(lock_file)) < 1800:
                logger.warning("DMS: Liquidation LOCK detected (GAP-89). Another node is already flattening. Standing down.")
                return []
            else:
                # Force take-over of stale lock
                logger.warning("DMS: Stale lock detected (>30m). Force-assuming leadership (GAP-90).")
                with open(lock_file, "w") as f:
                    f.write(f"LATENCY_CRITICAL node={socket.gethostname()} ts={datetime.now(timezone.utc).isoformat()} (FORCED)")
        except Exception as e:
            logger.error(f"DMS: Failed to create concurrency lock: {e}")

        flatten_results = []

        # --- Flatten IBKR positions ---
        ibkr_count = 0
        if self.ibkr_client:
            for attempt in range(1, _retries + 1):
                try:
                    if hasattr(self.ibkr_client, "isConnected") and self.ibkr_client.isConnected():
                        positions = list(self.ibkr_client.positions())
                        for pos in positions:
                            if pos.position != 0:
                                try:
                                    # GAP-23 FIX: Sovereign Shield (Aggressive Limit instead of Market)
                                    direction = "SELL" if pos.position > 0 else "BUY"
                                    shares = abs(pos.position)

                                    ticker = await asyncio.to_thread(self.ibkr_client.ticker, pos.contract)
                                    price = ticker.last or ticker.close or pos.avgCost

                                    from ib_insync import LimitOrder, MarketOrder
                                    if not price or price <= 0:
                                         logger.warning(f"DMS: Invalid price for {pos.contract.symbol}, falling back to market.")
                                         order = MarketOrder(direction, shares)
                                    else:
                                         # 5% buffer through the market (GAP-23 Hardened)
                                         lmt_price = price * (1.05 if direction == "BUY" else 0.95)
                                         order = LimitOrder(direction, shares, round(lmt_price, 4))
                                         logger.info(f"DMS [Shield]: Emergency Limit ({direction}) for {pos.contract.symbol} @ {lmt_price:.4f}")

                                    # ── TIMEOUT GUARD ──
                                    # Ensure qualification doesn't hang the DMS monitor
                                    await asyncio.wait_for(self.ibkr_client.qualifyContractsAsync(pos.contract), timeout=15.0)
                                    trade = self.ibkr_client.placeOrder(pos.contract, order)
                                    ibkr_count += 1

                                    order_desc = f"{round(lmt_price, 4)}" if isinstance(order, LimitOrder) else "MKT"
                                    flatten_results.append(f"IBKR: {direction} {shares} {pos.contract.symbol} @ {order_desc}")
                                    logger.critical(f"DMS FLATTEN: {direction} {shares} {pos.contract.symbol} OrderId={trade.order.orderId}")
                                except Exception as e:
                                    logger.error(f"DMS IBKR flatten {pos.contract.symbol} failed: {e}")
                                    flatten_results.append(f"IBKR FAILED: {pos.contract.symbol} - {e}")
                        break
                    else:
                        logger.warning(f"DMS: IBKR not connected (Attempt {attempt}/{_retries}) — attempting reconnect...")
                        try:
                            await asyncio.wait_for(
                                self.ibkr_client.connectAsync(host="127.0.0.1", port=self.ibkr_port, clientId=99),
                                timeout=10.0,
                            )
                            if self.ibkr_client.isConnected():
                                logger.info("DMS: IBKR reconnected successfully.")
                                break  # break reconnect-wait, retry outer for-loop
                        except Exception as e:
                            logger.error(f"DMS: IBKR reconnect failed: {e}")
                            if attempt == _retries:
                                flatten_results.append(f"IBKR RECONNECT FAILED AFTER ALL RETRIES: {e}")
                            await asyncio.sleep(2 ** attempt)

                except Exception as e:
                    logger.error(f"DMS IBKR flatten attempt failed: {e}")
                    if attempt == _retries:
                        flatten_results.append(f"IBKR FATAL ERROR: {e}")
                    await asyncio.sleep(2 ** attempt)

        # --- Flatten MT5 positions ---
        mt5_count = 0
        if self.mt5_client:
            try:

                # v1.0-beta-beta: Retry with 60s intervals (up to 3 attempts)
                for attempt in range(3):
                    positions = await asyncio.to_thread(mt5.positions_get)
                    if positions is None:
                        logger.warning(f"DMS MT5: No positions found (attempt {attempt + 1})")
                        if attempt < 2:
                            await asyncio.sleep(60)
                        continue

                    for pos in positions:
                        try:
                            # GAP-23 FIX: Add deviation guard and price fetch for MT5 Flatten
                            close_type = (
                                mt5.ORDER_TYPE_SELL
                                if pos.type == mt5.POSITION_TYPE_BUY
                                else mt5.ORDER_TYPE_BUY
                            )
                            symbol_info = await asyncio.to_thread(mt5.symbol_info, pos.symbol)
                            price = symbol_info.bid if close_type == mt5.ORDER_TYPE_SELL else symbol_info.ask

                            request = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "position": pos.ticket,
                                "symbol": pos.symbol,
                                "volume": pos.volume,
                                "type": close_type,
                                "price": price,
                                "deviation": 50, # Guard: Max 50 points of slippage
                                "magic": 234000,
                                "comment": "DMS emergency flatten",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": mt5.ORDER_FILLING_IOC,
                            }
                            result = await asyncio.to_thread(mt5.order_send, request)
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                mt5_count += 1
                                flatten_results.append(f"MT5: Closed {pos.symbol} vol={pos.volume}")
                                logger.critical(f"DMS FLATTEN MT5: {pos.symbol} vol={pos.volume}")
                            else:
                                error = result.comment if result else "unknown"
                                flatten_results.append(f"MT5 FAILED: {pos.symbol} - {error}")
                        except Exception as e:
                            logger.error(f"DMS MT5 close {pos.symbol} failed: {e}")

                    if mt5_count > 0:
                        break  # All closes sent — no need to retry

            except ImportError:
                logger.warning("DMS: MetaTrader5 not installed — cannot flatten MT5 positions")
            except Exception as e:
                logger.error(f"DMS MT5 flatten failed: {e}")
                flatten_results.append(f"MT5 ERROR: {e}")

        # --- Send flatten report ---
        total_flattened = ibkr_count + mt5_count
        report = (
            "🛑 <b>[STOP] DMS EMERGENCY FLATTEN EXECUTED [STOP]</b> 🛑\n\n"
            f"📉 <b>IBKR positions closed:</b> {ibkr_count}\n"
            f"📉 <b>MT5 positions closed:</b> {mt5_count}\n"
            f"📊 <b>Total:</b> {total_flattened}\n\n"
        )
        if flatten_results:
            report += "<b>Details:</b>\n"
            for r in flatten_results:
                report += f"• {r}\n"

        await self._send_telegram_message(report)
        logger.critical(f"DMS FLATTEN COMPLETE: {total_flattened} positions closed")

    async def send_status_ok(self) -> None:
        """Send hourly OK status message."""
        current_time = datetime.now(timezone.utc)

        hb_summary = ""
        for agent, ts in self.agent_heartbeats.items():
            age = (current_time - ts).total_seconds()
            hb_summary += f"• {agent}: {int(age)}s ago\n"

        message = (
            "✅ <b>[OK] Sovereign Status: OPERATIONAL [OK]</b> ✅\n\n"
            f"🕒 <b>Status Time:</b> {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚡ <b>Heartbeat Matrix:</b>\n{hb_summary}\n"
            f"⚙ <b>Timeout Threshold:</b> {self.timeout}s\n\n"
            "All intelligence nodes nominal."
        )

        await self._send_telegram_message(message)
        self.last_status_ok = current_time
        logger.info("Status OK message sent")

    async def run(self) -> None:
        """Main monitoring loop — check every 30s."""
        self.running = True
        logger.info("Dead Man Switch Monitor started")

        if not self.session:
            self.session = aiohttp.ClientSession()

        # Send initial status message
        await self._send_telegram_message(
            "🟢 <b>[START] Dead Man Switch Monitor Started [START]</b>\n\n"
            f"🕒 <b>Started at:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⚙ <b>Timeout:</b> {self.timeout}s\n"
            f"🛡 <b>Grace period:</b> {self.grace_period}s\n"
            f"💓 <b>Check interval:</b> 30s\n"
            f"🔌 <b>IBKR flatten:</b> {'enabled' if self.ibkr_client else 'disabled'}\n"
            f"🔌 <b>MT5 flatten:</b> {'enabled' if self.mt5_client else 'disabled'}"
        )

        try:
            while self.running:
                # Check for timeout
                await self.check_timeout()

                # Send hourly status OK message
                current_time = datetime.now(timezone.utc)
                time_since_status = (current_time - self.last_status_ok).total_seconds()

                if time_since_status >= 3600:
                    if not self.alert_sent:
                        await self.send_status_ok()

                # Wait 15 seconds before next check (GAP-85 Fix)
                await asyncio.sleep(15)

        except asyncio.CancelledError:
            logger.info("Monitor received cancellation signal")
            raise
        except Exception as e:
            logger.error(f"Error in DMS monitoring loop: {e}")
            raise
        finally:
            session = self.session
            if session:
                await session.close()
            logger.info("Dead Man Switch Monitor stopped")

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self.running = False
        logger.info("Stop requested for Dead Man Switch Monitor")
