import asyncio
import hashlib
import logging
import random
import time
from typing import Optional

import aiohttp
from vault import Vault

logger = logging.getLogger("telegram")

_alert_cache: dict[str, float] = {}  # {msg_hash: last_sent_timestamp}
_alert_lock = asyncio.Lock()
_last_sent_times: list[float] = []
_rate_limit_max = 20
_rate_limit_window = 60.0
_shared_session: Optional[aiohttp.ClientSession] = None

class SovereignTelegramBot:
    """
    Sovereign Telegram Bot with Elite Signal Sterilization and Async I/O.
    """
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = Vault.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
        self.url = f"{self.base_url}/bot{self.bot_token.strip()}/sendMessage"

    async def send_alert(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Transmits a message with Sterilization, Redaction, and Rate Limiting.
        """
        # 1. Sterilization
        allowed_prefixes = ["[EXECUTION]", "🚨", "⚠️", "🚀", "🛑", "🔴", "🟢", "⚪", "📢", "☣️", "SYSTEM CRITICAL", "TRADE FULLY CLOSED", "REJECTED", "🏛️", "SOVEREIGN", "MAIN", "BRAIN", "STATUS"]
        msg_upper = message.upper()
        is_elite = any(prefix.upper() in msg_upper for prefix in allowed_prefixes)
        is_error = any(term in msg_upper for term in ["ERROR", "FAILED", "EXCEPTION", "CRITICAL", "FATAL"])

        if not (is_elite or is_error):
            logger.debug(f"Sterilization: Suppressing non-essential signal: {message[:50]}...")
            return False

        # 2. Redaction
        secrets = Vault.get_all_redactable_values()
        for s in secrets:
            if s and len(s) > 3 and s in message:
                message = message.replace(s, "[REDACTED]")

        # 3. Deduplication & Rate Limiting
        msg_hash = hashlib.md5(message.encode()).hexdigest()
        async with _alert_lock:
            now = time.time()
            global _last_sent_times
            _last_sent_times = [t for t in _last_sent_times if now - t < _rate_limit_window]
            
            if len(_last_sent_times) >= _rate_limit_max:
                logger.warning(f"Telegram Global Rate Limit Hit ({_rate_limit_max} msgs/min).")
                return False

            last_sent = _alert_cache.get(msg_hash, 0)
            if now - last_sent < 30:
                logger.debug(f"Deduplication: Suppressing duplicate signal.")
                return False
            
            _alert_cache[msg_hash] = now
            _last_sent_times.append(now)

        # 4. Transmission
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        headers = {"User-Agent": random.choice(agents)}
        payload = {"chat_id": str(self.chat_id).strip(), "text": message, "parse_mode": parse_mode, "disable_web_page_preview": True}
        proxy = Vault.get("TELEGRAM_PROXY")

        try:
            global _shared_session
            if _shared_session is None or _shared_session.closed:
                _shared_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))
            
            async with _shared_session.post(self.url, json=payload, proxy=proxy, headers=headers) as resp:
                if resp.status == 200:
                    return True
                logger.error(f"Telegram API Error: {resp.status}")
                return False
        except Exception as e:
            logger.error(f"Telegram Transmission Failure: {e}")
            return False

    async def broadcast_trade(self, ticker: str, action: str, price: float, size: float, conviction: float):
        icon = "🟢" if action.upper() == "BUY" else "🔴"
        msg = f"{icon} <b>SOVEREIGN EXECUTION</b>\n\n"
        msg += f"<b>Asset:</b> {ticker}\n"
        msg += f"<b>Action:</b> {action.upper()}\n"
        msg += f"<b>Price:</b> ${price:,.4f}\n"
        msg += f"<b>Size:</b> {size} units\n"
        msg += f"<b>Conviction:</b> {conviction*100:.1f}%\n"
        await self.send_alert(msg, parse_mode="HTML")

async def send_telegram_alert(message: str, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
    token = bot_token or Vault.get("TELEGRAM_BOT_TOKEN")
    cid = chat_id or Vault.get("TELEGRAM_CHAT_ID")
    if token and cid:
        bot = SovereignTelegramBot(token, cid)
        return await bot.send_alert(message)
    return False
