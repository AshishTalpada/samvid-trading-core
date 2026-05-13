"""
src/safety.py

Safety helpers: emergency halt and runtime paper-mode enforcement.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from telegram_alerts import send_telegram_alert

logger = logging.getLogger("safety")


def _send_startup_alert(message: str) -> None:
    try:
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.call_soon_threadsafe(lambda: asyncio.create_task(send_telegram_alert(message)))
        else:
            asyncio.run(send_telegram_alert(message))
    except RuntimeError:
        logger.debug("Startup alert skipped because a running event loop prevented asyncio.run().")
    except Exception as exc:
        logger.error(f"Startup alert failed: {exc}")


def _force_paper_mode(system: Any, reason: str) -> None:
    system.mode = "paper"
    logger.warning(f"Startup Safety: {reason} — forcing paper mode")
    _send_startup_alert(
        "🛑 SOVEREIGN: Startup safety enforced PAPER mode. Live trading is disabled until explicitly authorized."
    )


def apply_runtime_safety(system: Any) -> None:
    """Apply aggressive startup safety checks to the running TradingSystem instance.

    - Enforce a paper-only trading mode unless explicitly allowed by Vault/Env
    - Set `system.mode` accordingly and log/notify if we force changes
    """
    try:
        import config
        from vault import Vault

        if getattr(config, "FORCED_PAPER_MODE", False):
            _force_paper_mode(system, "FORCED_PAPER_MODE active")
            return

        if os.environ.get("PAPER_MODE", "0").strip() == "1":
            _force_paper_mode(system, "PAPER_MODE=1 detected")
            return

        # Check Vault FIRST (authoritative — .env file is loaded into Vault, not os.environ)
        # Then fall back to os.environ for container/CI overrides.
        env_mode = Vault.get("TRADING_MODE", "").strip().lower()
        if not env_mode:
            env_mode = os.environ.get("TRADING_MODE", "").strip().lower()

        allow_live = (
            Vault.get("ALLOW_FORCE_LIVE", "0").strip() == "1"
            or os.environ.get("ALLOW_FORCE_LIVE", "0").strip() == "1"
        )

        if env_mode:
            if env_mode not in ("paper", "ibkr_paper", "live"):
                logger.warning(
                    f"Startup Safety: Invalid TRADING_MODE '{env_mode}' ignored. Defaulting to paper mode."
                )
                env_mode = ""
            elif env_mode == "live" and not allow_live:
                logger.warning(
                    "Startup Safety: TRADING_MODE=live requires ALLOW_FORCE_LIVE=1. Defaulting to paper mode."
                )
                env_mode = ""

        if env_mode:
            system.mode = env_mode
            logger.info(f"Startup Safety: TRADING_MODE set to '{env_mode}'")
            return

        if not allow_live:
            _force_paper_mode(system, "No explicit live authorization found")
        else:
            logger.warning(
                "Startup Safety: ALLOW_FORCE_LIVE detected — proceeding with configured trading mode."
            )

    except Exception as e:
        logger.error(f"Safety startup enforcement failed: {e}")


def EMERGENCY_HALT(reason: str = "EMERGENCY HALT invoked") -> None:
    """Trigger an emergency halt: stop trading, notify operators.

    This is safe to call from sync or async context. It will attempt to call the
    global TradingStateManager.halt() if available, and send an async Telegram alert.
    """
    try:
        # Attempt to import TradingStateManager if available
        try:
            from trading_state import TradingStateManager

            TradingStateManager.halt(f"EMERGENCY HALT: {reason}")
            logger.critical(f"EMERGENCY HALT invoked via TradingStateManager: {reason}")
        except Exception:
            logger.critical(f"EMERGENCY HALT: TradingStateManager not available — reason: {reason}")

        # Fire-and-forget Telegram alert
        try:
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(send_telegram_alert(f"🛑 EMERGENCY HALT: {reason}"))
                )
            else:
                asyncio.run(send_telegram_alert(f"🛑 EMERGENCY HALT: {reason}"))
        except RuntimeError:
            logger.debug("Emergency alert skipped because a running event loop prevented asyncio.run().")
        except Exception:
            logger.error("Failed to send emergency Telegram alert")

    except Exception as e:
        logger.error(f"EMERGENCY_HALT failed: {e}")
