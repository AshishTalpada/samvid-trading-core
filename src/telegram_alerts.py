import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

class SovereignTelegramBot:
    """
    Direct Telegram API integration for ultra-fast, push-notification mobile alerts.
    Does not use heavy wrapper libraries like python-telegram-bot; interacts directly
    with api.telegram.org via HTTP session pooling for minimal latency.
    """
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        # Use session pooling to keep the TCP connection alive (reduces SSL handshake overhead)
        self.session = requests.Session()

        # Rate limiting state
        self.last_msg_time = 0.0
        self.msg_count_this_minute = 0

    def send_alert(self, message: str, parse_mode: str = "MarkdownV2") -> bool:
        """
        Transmits a message to the encrypted Telegram channel.
        Includes built-in rate-limiting logic to avoid Telegram API 429 Too Many Requests errors.
        """
        # Telegram limit: Max 20 messages per minute per group
        current_time = time.time()
        if current_time - self.last_msg_time > 60:
            self.msg_count_this_minute = 0

        if self.msg_count_this_minute >= 19:
            logger.warning("[TELEGRAM] Rate limit approaching. Dropping non-critical message.")
            return False

        url = f"{self.base_url}/sendMessage"

        # Escape characters required for MarkdownV2
        if parse_mode == "MarkdownV2":
            escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in escape_chars:
                message = message.replace(char, f"\\{char}")

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            # Short timeout. We don't want the trading loop hanging on a webhook.
            response = self.session.post(url, json=payload, timeout=2.0)

            if response.status_code == 200:
                self.last_msg_time = current_time
                self.msg_count_this_minute += 1
                return True
            else:
                logger.error(f"[TELEGRAM] API Error: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"[TELEGRAM] Network failure during transmission: {e}")
            return False

    def broadcast_trade(self, ticker: str, action: str, price: float, size: float, conviction: float):
        """Formats and fires a high-priority trade execution alert."""
        icon = "🟢" if action.upper() == "BUY" else "🔴"
        msg = f"{icon} *SOVEREIGN EXECUTION*\n\n"
        msg += f"*Asset:* {ticker}\n"
        msg += f"*Action:* {action.upper()}\n"
        msg += f"*Price:* ${price:,.4f}\n"
        msg += f"*Size:* {size} units\n"
        msg += f"*Conviction:* {conviction*100:.1f}%\n"

        self.send_alert(msg)

def send_telegram_alert(message: str, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
    """Global utility to send alerts without manually managing bot instances."""
    from vault import Vault
    token = bot_token or Vault.get("TELEGRAM_BOT_TOKEN")
    cid = chat_id or Vault.get("TELEGRAM_CHAT_ID")
    if token and cid:
        bot = SovereignTelegramBot(token, cid)
        return bot.send_alert(message)
    return False
