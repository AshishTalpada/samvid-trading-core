import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class InvariantBounds:
    min_val: float
    max_val: float
    description: str

class RiskInvariants:
    """
    GAP-86: Autonomous Risk Corruption Shield.
    Ensures that critical risk constants haven't been tampered with
    by an AI agent or a bug.
    """

    # Hardcoded Sanctity Bounds
    SANCTITY_BOUNDS = {
        "SYSTEM_MAX_RISK": InvariantBounds(0.005, 0.05, "Maximum total system risk (0.5% - 5%)"),
        "RISK_PER_TRADE_PCT": InvariantBounds(0.001, 0.02, "Risk per trade (0.1% - 2%)"),
        "FTMO_DAILY_LIMIT": InvariantBounds(0.01, 0.05, "Daily loss limit (1% - 5%)"),
        "MAX_TRADES_PER_DAY": InvariantBounds(1, 50, "Max trades per day (1 - 50)"),
        "BELIEF_EXIT_THRESHOLD": InvariantBounds(0.1, 0.5, "Belief exit threshold (10% - 50%)"),
    }

    @classmethod
    def verify_config(cls) -> bool:
        """
        Verify that src/config.py values are within sanity bounds.
        Returns False if corruption is detected.
        """
        import config
        corrupted = False

        for key, bounds in cls.SANCTITY_BOUNDS.items():
            val = getattr(config, key, None)
            if val is None:
                logger.critical(f"RISK CORRUPTION: Constant '{key}' is MISSING from config!")
                corrupted = True
                continue

            if not (bounds.min_val <= val <= bounds.max_val):
                logger.critical(
                    f"RISK CORRUPTION: '{key}' is {val}, which is outside safe bounds "
                    f"[{bounds.min_val}, {bounds.max_val}]! ({bounds.description})"
                )
                corrupted = True

        return not corrupted

    @classmethod
    def is_mutation_safe(cls, key: str, proposed_value: float) -> bool:
        """
        Verify that a proposed evolutionary mutation is within safety bounds.
        Prevents Agent C from becoming over-aggressive or dangerously passive.
        """
        bounds = cls.SANCTITY_BOUNDS.get(key)
        if not bounds:
            logger.warning(f"INVARIANT WARNING: No bounds defined for '{key}'. Mutation BLOCKED by default.")
            return False

        if bounds.min_val <= proposed_value <= bounds.max_val:
            return True

        logger.critical(
            f"INVARIANT VETO: Mutation for '{key}' to {proposed_value} is OUTSIDE SANCTITY BOUNDS "
            f"[{bounds.min_val}, {bounds.max_val}]! {bounds.description}"
        )
        return False

    @classmethod
    def audit_trade_parameters(cls, risk_dollars: float, balance: float) -> bool:
        """
        Final safety check before order transmission.
        Ensures the sizer didn't return an insane value.
        """
        if balance <= 0:
            return False

        risk_pct = risk_dollars / balance
        # Absolute maximum risk per trade invariant: 3%
        if risk_pct > 0.03:
            logger.critical(f"RISK VIOLATION: Proposed trade risk {risk_pct:.2%} exceeds 3% hard invariant!")
            return False

        return True
