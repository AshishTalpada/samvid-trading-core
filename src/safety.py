"""
src/safety.py

Safety helpers: emergency halt and runtime paper-mode enforcement.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from telegram_alerts import send_telegram_alert

logger = logging.getLogger("safety")
DEFAULT_PROMOTION_READINESS_REPORT = Path("data/promotion_readiness_report.json")


def _send_safety_alert(message: str, category: str = "Safety") -> None:
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
        logger.debug(
            f"{category} alert skipped because a running event loop prevented asyncio.run()."
        )
    except Exception as exc:
        logger.error(f"{category} alert failed: {exc}")


def _force_paper_mode(system: Any, reason: str) -> None:
    system.mode = "paper"
    logger.warning(f"Startup Safety: {reason} — forcing paper mode")
    _send_safety_alert(
        " SOVEREIGN: Startup safety enforced PAPER mode. Live trading is disabled until explicitly authorized.",
        category="Startup",
    )


def _promotion_gate_required(vault: Any) -> bool:
    raw = os.environ.get("SOVEREIGN_REQUIRE_PROMOTION_FOR_LIVE", "").strip()
    if not raw:
        raw = vault.get("SOVEREIGN_REQUIRE_PROMOTION_FOR_LIVE", "1").strip()
    return raw != "0"


def _promotion_readiness_path(vault: Any) -> Path:
    raw = os.environ.get("SOVEREIGN_PROMOTION_READINESS_REPORT", "").strip()
    if not raw:
        raw = vault.get(
            "SOVEREIGN_PROMOTION_READINESS_REPORT",
            str(DEFAULT_PROMOTION_READINESS_REPORT),
        ).strip()
    return Path(raw or DEFAULT_PROMOTION_READINESS_REPORT)


def _promotion_readiness_approved(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"promotion readiness report missing: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"promotion readiness report unreadable: {type(exc).__name__}: {exc}"
    if payload.get("approved") is True:
        return True, "promotion readiness approved"
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        return False, "; ".join(str(item) for item in blockers[:5])
    return False, "promotion readiness report is not approved"


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
        env_mode = os.environ.get("TRADING_MODE", "").strip().lower()
        if not env_mode and os.environ.get("SOVEREIGN_SKIP_PID_CHECK", "0") != "1":
            env_mode = Vault.get("TRADING_MODE", "").strip().lower()

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
            elif (
                env_mode == "live"
                and allow_live
                and _promotion_gate_required(Vault)
            ):
                approved, reason = _promotion_readiness_approved(_promotion_readiness_path(Vault))
                if not approved:
                    _force_paper_mode(
                        system,
                        f"TRADING_MODE=live blocked by promotion readiness gate: {reason}",
                    )
                    return

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
        # Fail CLOSED: if the safety gate itself errors we must never leave the system in
        # a potentially-live mode that bypassed the ALLOW_FORCE_LIVE authorization check.
        logger.error(f"Safety startup enforcement failed: {e} — forcing paper mode")
        try:
            system.mode = "paper"
        except Exception as set_exc:
            logger.critical(f"Safety: could not force paper mode after failure: {set_exc}")


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
        _send_safety_alert(f" EMERGENCY HALT: {reason}", category="Emergency")

    except Exception as e:
        logger.error(f"EMERGENCY_HALT failed: {e}")
