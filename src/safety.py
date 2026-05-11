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


def apply_runtime_safety(system: Any) -> None:
    """Apply aggressive startup safety checks to the running TradingSystem instance.

    - Enforce a paper-only trading mode unless explicitly allowed by Vault/Env
    - Set `system.mode` accordingly and log/notify if we force changes
    """
    try:
        # Priority 1: If the code-level forced flag is set in config, honor it
        import config

        if getattr(config, "FORCED_PAPER_MODE", False):
            system.mode = "paper"
            logger.warning("Startup Safety: FORCED_PAPER_MODE active — forcing paper mode")
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    loop.create_task(
                        send_telegram_alert(
                            "🛑 SOVEREIGN: FORCED_PAPER_MODE active — live trading disabled at startup."
                        )
                    )
                else:
                    logger.debug("No running event loop; skipping startup telegram alert")
            except Exception:
                pass
            return

        # Next, check environment override
        env_mode = os.environ.get("TRADING_MODE")
        if env_mode:
            env_mode = env_mode.strip().lower()
            if env_mode in ("paper", "ibkr_paper"):
                system.mode = env_mode
                logger.info(f"Startup Safety: TRADING_MODE environment set to '{env_mode}'")
                return

        # Lastly, check Vault value if available (the system already reads from Vault in main)
        # If none found or unsafe value present, default to paper
        # This is an intentionally conservative default to protect capital.
        # Acceptable live modes must be explicitly authorized by setting
        # the environment variable 'ALLOW_FORCE_LIVE' to '1' and TRADING_MODE to a live mode.
        allow_live = os.environ.get("ALLOW_FORCE_LIVE", "0").strip() == "1"
        if not allow_live:
            system.mode = "paper"
            logger.warning(
                "Startup Safety: No explicit live authorization found — defaulting to PAPER mode."
            )
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    loop.create_task(
                        send_telegram_alert(
                            "🛑 SOVEREIGN: Startup enforced PAPER mode. Set ALLOW_FORCE_LIVE=1 to override with caution."
                        )
                    )
                else:
                    logger.debug("No running event loop; skipping startup telegram alert")
            except Exception:
                pass
        else:
            # Allow the mode from Vault/main to remain as-is (less intrusive)
            logger.warning("Startup Safety: ALLOW_FORCE_LIVE detected — proceeding with configured trading mode.")

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
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda: asyncio.create_task(send_telegram_alert(f"🛑 EMERGENCY HALT: {reason}"))
            )
        except Exception:
            # If no event loop, create a new task asynchronously
            try:
                asyncio.run(send_telegram_alert(f"🛑 EMERGENCY HALT: {reason}"))
            except Exception:
                logger.error("Failed to send emergency Telegram alert")

    except Exception as e:
        logger.error(f"EMERGENCY_HALT failed: {e}")
