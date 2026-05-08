import asyncio
import logging

import aiohttp

from vault import Vault

logger = logging.getLogger("telegram")

_alert_cache: dict[str, float] = {}  # {msg_hash: last_sent_timestamp}
_alert_lock = asyncio.Lock()
_last_sent_times: list[float] = []
_rate_limit_max = 20
_rate_limit_window = 60.0
_shared_session: aiohttp.ClientSession | None = None


async def send_telegram_alert(message: str) -> None:
    """
    Sends a Telegram alert with Elite Signal Sterilization.
    Blocks routine pattern noise and 'Phantom' calls.
    """
    allowed_prefixes = [
        "[EXECUTION]",
        "🚨",
        "⚠️",
        "🚀",
        "🛑",
        "🔴",
        "🟢",
        "🟢",
        "⚪",
        "📢",
        "☣️",
        "SYSTEM CRITICAL",
        "TRADE FULLY CLOSED",
        "REJECTED",
        "🏛️",
        "SOVEREIGN",
        "MAIN",
        "BRAIN",
        "STATUS",
    ]

    msg_upper = message.upper()
    is_elite = any(prefix.upper() in msg_upper for prefix in allowed_prefixes)
    is_error = any(
        term in msg_upper for term in ["ERROR", "FAILED", "EXCEPTION", "CRITICAL", "FATAL"]
    )

    if not (is_elite or is_error):
        logger.debug(f"Sterilization: Suppressing non-essential signal: {message[:50]}...")
        return

    import hashlib

    msg_hash = hashlib.md5(message.encode()).hexdigest()  # nosec B324
    async with _alert_lock:
        now = asyncio.get_event_loop().time()

        global _last_sent_times
        # Prune times outside the window
        _last_sent_times = [t for t in _last_sent_times if now - t < _rate_limit_window]
        if len(_last_sent_times) >= _rate_limit_max:
            logger.warning(
                f"Telegram Global Rate Limit Hit ({_rate_limit_max} msgs/min). Suppressing alert."
            )
            return

        last_sent = _alert_cache.get(msg_hash, 0)
        if now - last_sent < 30:  # 30 seconds idempotency
            logger.debug(
                f"Deduplication: Suppressing duplicate signal ({now - last_sent:.1f}s since last)"
            )
            return
        _alert_cache[msg_hash] = now
        _last_sent_times.append(now)

        # Cleanup old cache entries (older than 1 hour)
        to_del = [k for k, t in _alert_cache.items() if now - t > 3600]
        for k in to_del:
            del _alert_cache[k]

    token = Vault.get("TELEGRAM_BOT_TOKEN")
    chat_id = Vault.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        return

    import random

    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    headers = {"User-Agent": random.choice(agents)}

    redacted_message = message
    secrets = Vault.get_all_redactable_values()
    for s in secrets:
        if s and len(s) > 3 and s in redacted_message:
            redacted_message = redacted_message.replace(s, "[REDACTED]")

    base_url = (Vault.get("TELEGRAM_API_URL") or "https://api.telegram.org").rstrip("/")
    url = f"{base_url}/bot{token.strip()}/sendMessage"
    payload = {"chat_id": chat_id.strip(), "text": redacted_message, "parse_mode": "HTML"}

    proxy = Vault.get("TELEGRAM_PROXY")

    max_retries = 3
    base_delay = 2

    try:
        global _shared_session
        if _shared_session is None or _shared_session.closed:
            _shared_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10.0))

        session = _shared_session
        for attempt in range(max_retries):
            try:
                # Pass randomized headers per request to the shared session
                async with session.post(url, json=payload, proxy=proxy, headers=headers) as resp:
                    if resp.status == 200:
                        return
                    elif resp.status == 429:  # Rate limit
                        await asyncio.sleep(10)
                        continue
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send telegram alert after {max_retries} attempts: {e}")
                else:
                    await asyncio.sleep(base_delay * (attempt + 1))
    except Exception as e:
        logger.error(f"Telegram session management failed: {e}")
