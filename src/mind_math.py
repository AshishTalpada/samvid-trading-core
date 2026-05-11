import logging
from typing import Any

logger = logging.getLogger(__name__)


class MindMath:
    """
    Agent M: The Deterministic Mathematical Auditor.
    ZERO AI. Uses pure geometry, ATR, and fixed logic to VETO hallucinations.
    Ensures that every AI-proposed trade obeys the 'Geometry of Risk'.
    """

    def __init__(self, bridge: Any = None, **kwargs) -> None:
        self.bridge = bridge
        if self.bridge:
            self.bridge.register_tool("validate_geometry", self._tool_validate_geometry)

    async def _tool_validate_geometry(
        self,
        direction: str,
        entry_price: float,
        stop_price: float,
        target_price: float,
        atr: float | None = None,
    ) -> dict[str, Any]:
        """
        Deterministic verification of trade geometry.
        Vetoes trades with inverted stops, zero R:R, or ATR violations.
        """
        from decimal import Decimal, getcontext

        getcontext().prec = 28

        try:
            # 1. Convert to Decimal to prevent floating point drift
            d_entry = Decimal(str(entry_price))
            d_stop = Decimal(str(stop_price))
            d_target = Decimal(str(target_price))
            d_atr = Decimal(str(atr)) if atr is not None else None

            # 2. Directional Integrity Check
            if direction.upper() == "LONG":
                if d_stop >= d_entry:
                    return {
                        "valid": False,
                        "reason": "Deterministic VETO: Stop loss must be BELOW entry for Longs.",
                    }
                if d_target <= d_entry:
                    return {
                        "valid": False,
                        "reason": "Deterministic VETO: Target must be ABOVE entry for Longs.",
                    }
            elif direction.upper() == "SHORT":
                if d_stop <= d_entry:
                    return {
                        "valid": False,
                        "reason": "Deterministic VETO: Stop loss must be ABOVE entry for Shorts.",
                    }
                if d_target >= d_entry:
                    return {
                        "valid": False,
                        "reason": "Deterministic VETO: Target must be BELOW entry for Shorts.",
                    }

            # 3. Minimum R:R Ratio Check (Strict 1.5 Floor for Sovereign)
            risk = abs(d_entry - d_stop)
            reward = abs(d_target - d_entry)

            if risk == 0:
                return {
                    "valid": False,
                    "reason": "Deterministic VETO: Zero risk calculation detected.",
                }

            rr_ratio = reward / risk
            if rr_ratio < Decimal("1.5"):
                return {
                    "valid": False,
                    "reason": f"Deterministic VETO: R:R ratio {float(rr_ratio):.2f} below 1.5 Sovereign Floor.",
                }

            # 4. ATR Validity Check
            if d_atr is not None:
                # 4.1 Zero ATR Check: Prevent trading in stagnant/illiquid pools
                if d_atr <= (d_entry * Decimal("1e-7")) or d_atr <= 0:
                    return {
                        "valid": False,
                        "reason": "Deterministic VETO: Zero/Near-Zero ATR detected. Market is stagnant or feed is dead.",
                    }

                # 4.2 Proximity Check (Prevent 'Tight-Stop' Hallucinations)
                # Stop must be at least 0.5 ATR away to survive noise
                if risk < (d_atr * Decimal("0.5")):
                    return {
                        "valid": False,
                        "reason": f"Deterministic VETO: Stop distance ({float(risk):.4f}) is < 0.5 ATR ({float(d_atr) * 0.5:.4f}). High noise risk.",
                    }

            logger.info(f"MindMath: Geometry VALIDATED (R:R: {float(rr_ratio):.2f})")
            return {"valid": True, "rr_ratio": float(rr_ratio)}

        except Exception as e:
            logger.error(f"MindMath Error: {e}")
            return {"valid": False, "reason": f"Math Error during validation: {e}"}
