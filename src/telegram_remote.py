import time
import asyncio
import logging
from datetime import datetime

import aiohttp

from intelligence_bus import get_bus
from vault import Vault

logger = logging.getLogger("telegram_remote")


class TelegramRemote:
    """
    Sovereign Remote Control.
    Enables remote intervention (Panic, Status, Dhatu Override) via Telegram polling.
    Designed for low-overhead operation on hardware-constrained systems.
    """

    def __init__(self):
        self.token = Vault.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = str(Vault.get("TELEGRAM_CHAT_ID", "")).strip()
        self.pin = Vault.get("TELEGRAM_PIN", "0000")
        self.bus = get_bus()
        self.last_update_id = 0
        self.is_running = False
        self.session = None
        self.last_auth_time = 0.0
        self._auth_attempts = 0
        self._last_auth_attempt_time = 0.0

        # Internal snapshot for /status
        self.current_regime = "UNKNOWN"
        self.current_dhatu = "Sthiti"
        self.snapshot_time = 0.0
        self.open_pnl = 0.0
        self.positions_count = 0
        self.vram_status = "STABLE"

    async def start(self):
        """Start the remote listener loop."""
        if self.is_running:
            logger.debug("TelegramRemote: Already running.")
            return

        if not self.token or not self.chat_id:
            logger.warning("TelegramRemote: Token or ChatID missing. Remote control DISABLED.")
            return

        logger.info("🏛️ Sovereign Remote: Listening for high-priority commands...")
        self.is_running = True
        self.session = aiohttp.ClientSession()

        # Subscribe to bus to maintain an internal "Status Snapshot" for zero-latency replies
        self.bus.on("oracle.state", self._update_dhatu)
        self.bus.on("trade.exit", self._update_stats)
        self.bus.on("notification.telegram", self._handle_broadcast)

        asyncio.create_task(self._poll_loop())

    async def stop(self):
        """Graceful shutdown."""
        self.is_running = False
        if self.session:
            await self.session.close()

    async def _update_dhatu(self, payload):
        from time_sync import TimeSync

        self.current_dhatu = payload.get("dhatu", "Sthiti")
        self.current_regime = payload.get("regime", "UNKNOWN")
        self.snapshot_time = TimeSync.now().timestamp()

    async def _update_stats(self, payload):
        # We'll rely on the Brain to provide full stats for /status,
        # but we track the last exit for immediate feedback.
        pass

    async def _poll_loop(self):
        """Main polling loop for Telegram updates."""
        api_base = Vault.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
        url = f"{api_base}/bot{self.token}/getUpdates"

        try:
            async with self.session.get(f"{api_base}/bot{self.token}/deleteWebhook") as dw:
                await dw.json()
        except Exception:
            pass

        while self.is_running:
            try:
                params = {"offset": self.last_update_id + 1, "timeout": 30}
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for update in data.get("result", []):
                            self.last_update_id = update["update_id"]
                            await self._handle_update(update)
                    else:
                        logger.error(f"TelegramRemote: Error {resp.status}")
                        await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"TelegramRemote Poll Error: {e}")
                await asyncio.sleep(5)

            await asyncio.sleep(1)

    async def _handle_update(self, update):
        """Process an incoming message or command."""
        message = update.get("message")
        if not message:
            return

        text = message.get("text", "")
        sender_chat_id = str(message.get("chat", {}).get("id"))

        # AUTH CHECK: Only respond to the authorized chat ID
        # Handle case where Vault might return a list of authorized IDs (comma-separated)
        authorized_ids = [cid.strip() for cid in self.chat_id.split(",") if cid.strip()]
        if sender_chat_id not in authorized_ids:
            logger.warning(f"UNAUTHORIZED remote attempt from {sender_chat_id}")
            return

        if not text.startswith("/"):
            return

        cmd_parts = text.split()
        command = cmd_parts[0].lower()
        args = cmd_parts[1:]
        from time_sync import TimeSync

        now = TimeSync.now().timestamp()

        logger.warning(f"🏛️ Sovereign Remote: Executing command [{command}]")

        if command == "/auth":
            if self._auth_attempts >= 5 and (now - self._last_auth_attempt_time) < 300:
                await self._send_message(
                    "❌ <b>LOCKED</b>: Too many failed attempts. Try again in 5 minutes.",
                    sender_chat_id,
                )
                return

            self._last_auth_attempt_time = now
            if args and args[0] == str(self.pin):
                self.last_auth_time = now
                self._auth_attempts = 0  # Reset on success
                await self._send_message(
                    "✅ <b>AUTH SUCCESS</b>: Critical commands unlocked for 5 mins.", sender_chat_id
                )
            else:
                self._auth_attempts += 1
                await self._send_message(
                    f"❌ <b>AUTH FAILED</b>: Invalid PIN. ({self._auth_attempts}/5)", sender_chat_id
                )
            return

        if command == "/status":
            await self._send_status(sender_chat_id)
        elif command == "/panic" or command == "/dhatu":
            if (now - self.last_auth_time) < 300:
                if command == "/panic":
                    await self._execute_panic(sender_chat_id)
                elif command == "/dhatu":
                    await self._execute_dhatu_override(args, sender_chat_id)
            else:
                await self._send_message(
                    "🔒 <b>LOCKED</b>: Please `/auth <PIN>` to execute high-privilege commands.",
                    sender_chat_id,
                )
        elif command == "/ping":
            await self._send_message(
                "🏓 <b>PONG</b>: Sovereign Intelligence is Active.", sender_chat_id
            )
        else:
            await self._send_message(
                "❓ Unknown command. Available: /status, /panic, /dhatu, /ping, /auth",
                sender_chat_id,
            )

    async def _send_status(self, chat_id: str):
        """Ask the bus for current telemetry and reply."""
        await self.bus.publish(
            "command.remote", {"cmd": "status", "ts": time.time_ns()}
        )
        await asyncio.sleep(0.5)

        from time_sync import TimeSync

        now = TimeSync.now().timestamp()
        age = now - self.snapshot_time if self.snapshot_time > 0 else 999
        stale_warning = " ⚠️ STALE" if age > 30 else ""

        msg = (
            "🏛️ <b>Sovereign Status</b>\n"
            f"───────────────────\n"
            f"Regime: `{self.current_regime}`\n"
            f"Dhatu: `{self.current_dhatu}`\n"
            f"Data Age: {int(age)}s{stale_warning}\n"
            f"Time: {datetime.now().strftime('%H:%M:%S')}\n"
            f"───────────────────\n"
            f"Reply `/status` for real-time telemetry."
        )
        await self._send_message(msg, chat_id)

    async def _execute_panic(self, chat_id: str):
        """Trigger the Sovereign Panic Shield."""
        await self._send_message(
            "⚠️ <b>PANIC INITIATED</b>: Broadcasting Emergency Liquidation Command...", chat_id
        )
        await self.bus.publish("command.remote", {"cmd": "panic", "ts": time.time_ns()})

    async def _execute_dhatu_override(self, args, chat_id: str):
        """Force a Dhatu state (e.g., /dhatu ABHAVA)."""
        if not args:
            await self._send_message("Usage: `/dhatu [ABHAVA|SHANTI|VRIDDHI]`", chat_id)
            return

        target = args[0].upper()
        if target not in ["ABHAVA", "STHITI", "VRIDDHI", "SHANTI"]:
            await self._send_message("❌ Invalid Dhatu target.", chat_id)
            return

        await self._send_message(
            f"🔄 <b>OVERRIDE</b>: Forcing system state to `{target}`...", chat_id
        )
        await self.bus.publish("command.remote", {"cmd": "dhatu_override", "target": target})

    async def _handle_broadcast(self, payload):
        """Handle incoming broadcast messages from the Brain."""
        msg = payload.get("message")
        if msg:
            await self._send_message(msg)

    async def _send_message(self, text: str, chat_id: str | None = None):
        """Internal helper to reply via Telegram."""
        if not self.session:
            return

        # Priority: explicit chat_id > first authorized ID from Vault
        target_id = chat_id or self.chat_id.split(",")[0].strip()
        if not target_id:
            logger.warning("TelegramRemote: Cannot send message, no target chat_id.")
            return

        redacted_text = text
        secrets = Vault.get_all_redactable_values()
        for s in secrets:
            if s and len(s) > 3 and s in redacted_text:
                redacted_text = redacted_text.replace(s, "[REDACTED]")

        api_base = Vault.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
        url = f"{api_base}/bot{self.token}/sendMessage"
        payload = {"chat_id": target_id, "text": redacted_text, "parse_mode": "HTML"}
        try:
            async with self.session.post(url, json=payload, timeout=5) as resp:
                if resp.status != 200:
                    logger.error(f"Failed to reply: {resp.status}")
        except Exception as e:
            logger.error(f"Error sending reply: {e}")


# Global instance
_remote = None


def get_remote():
    global _remote
    if _remote is None:
        _remote = TelegramRemote()
    return _remote
