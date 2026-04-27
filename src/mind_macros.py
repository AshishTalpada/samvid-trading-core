import logging
from typing import Final

logger = logging.getLogger(__name__)

# --- MACRO HUB: THE SIGNED GUARDRAILS (Samvid v1.0-beta-beta-beta) ---
# These are 'Hardcoded System Truths' that even the Masters Mind cannot bypass.
# Inspired by src/shims/macro.ts and path hijacking protection.


class MindMacros:
    """
    A Central Allowlist and Global State Hub for the Matrix.
    Acts as the 'Absolute Guardrail' against hallucinatory healing.
    """

    # 1. TOOL ALLOWLIST (Minds can only call these certified tool chains)
    CERTIFIED_TOOLS: Final[set[str]] = {
        "heal_code",
        "check_syntax",
        "pause_and_reason",
        "simulate_outcome",
        "fetch_sentiment",
        "optimize_thresholds",
        "shadow_test",
        "lock_peak",
        "report_bleed",
        "housekeeping",
        "reboot_service",
        "find_executable",
        "sovereign_flush",
        "get_account_status",
        "get_open_positions"
    }

    # GAP-64 FIX: Sensitive Tool Handshake requirement
    # These tools require a secondary 'justification' and 'DoubleHandshake' logic.
    SENSITIVE_TOOLS: Final[set[str]] = {
        "heal_code",
        "reboot_service",
        "run_system_command"
    }

    # 2. SYSTEM INVARIANTS (The 'Constants of Truth')
    ABSOLUTE_MAX_LOSS_PERCENT: Final[float] = 2.0
    COMMISSION_BUFFER_PERCENT: Final[float] = 0.1 # Reserve 10bps for fees (GAP-65)
    REQUIRED_CANDLE_COUNT: Final[int] = 50
    FORCED_LATENCY_GATE_MS: Final[int] = 250

    @staticmethod
    def is_tool_signed(tool_name: str) -> bool:
        """Verifies if a tool invocation is within the certified safety envelope."""
        if tool_name not in MindMacros.CERTIFIED_TOOLS:
            logger.error(
                f"SECURITY BREACH: Mind attempted to call SIGNED tool '{tool_name}' — BLOCKED."
            )
            return False
        return True

    @staticmethod
    def validate_risk(percent_loss: float, symbol: str = "SPY") -> bool:
        """
        Hardcoded check to prevent 'Absolute Catastrophe'.
        GAP-166: Dynamic cap for high-volatility assets (BTC/ETH).
        """
        limit = MindMacros.ABSOLUTE_MAX_LOSS_PERCENT

        # Crypto-Specific Tolerance (Sovereign v1.0-beta-beta)
        if any(crypto in symbol.upper() for crypto in ["BTC", "ETH", "SOL", "COIN"]):
            limit = 5.0 # Allow up to 5% for high-ATR assets

        total_risk = percent_loss + MindMacros.COMMISSION_BUFFER_PERCENT
        if total_risk > limit:
            logger.critical(
                f"GUARDRAIL TRIPPED: Potential risk {total_risk:.2f}% (incl. fees) exceeds hard limit of {limit}% for {symbol}."
            )
            return False
        return True
