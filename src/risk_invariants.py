import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class OrderThrottler:
    """
    Token-bucket order rate limiter.
    Prevents runaway loops from flooding the broker API.

    Default: max 30 orders per 60 seconds.
    """

    def __init__(self, max_orders: int = 30, per_seconds: int = 60):
        self._max = max_orders
        self._window = timedelta(seconds=per_seconds)
        self._timestamps: deque[datetime] = deque()

    def can_submit(self) -> bool:
        """Return True if an order may be submitted, False if throttled."""
        now = datetime.now(timezone.utc)
        # Evict timestamps outside the sliding window
        while self._timestamps and (now - self._timestamps[0]) > self._window:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._max:
            logger.error(
                f"ORDER THROTTLED: {self._max} orders already submitted in "
                f"{self._window.seconds}s. Standing down."
            )
            return False
        self._timestamps.append(now)
        return True

    def reset(self) -> None:
        self._timestamps.clear()


# Module-level singleton — import directly
ORDER_THROTTLER = OrderThrottler()


@dataclass
class InvariantBounds:
    min_val: float
    max_val: float
    description: str


class RiskInvariants:
    """
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

    # Hard notional caps per instrument (USD). DEFAULT applies to all unlisted symbols.
    MAX_NOTIONAL_PER_ORDER: dict[str, float] = {
        # Large-cap ETFs
        "SPY": 200_000,
        "QQQ": 160_000,
        "DIA": 120_000,
        "IWM": 100_000,
        # Large-cap tech
        "MSFT": 100_000,
        "AAPL": 100_000,
        "GOOGL": 80_000,
        "AMZN": 80_000,
        "META": 80_000,
        "NVDA": 80_000,
        "AVGO": 60_000,
        "AMD": 60_000,
        # High-vol / mid-cap — tighter caps
        "TSLA": 60_000,
        "NFLX": 60_000,
        "COST": 60_000,
        "GS": 60_000,
        "JPM": 60_000,
        "MA": 60_000,
        "V": 60_000,
        "WMT": 60_000,
        "ARM": 40_000,
        "MU": 40_000,
        "PLTR": 30_000,  # High volatility
        "MSTR": 30_000,  # BTC-correlated, extreme volatility
        "COIN": 20_000,  # Crypto-proxy, extreme intraday swings
        "SMCI": 20_000,  # Micro-cap, extreme volatility
        "DEFAULT": 40_000,
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
            logger.warning(
                f"INVARIANT WARNING: No bounds defined for '{key}'. Mutation BLOCKED by default."
            )
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
            logger.critical(
                f"RISK VIOLATION: Proposed trade risk {risk_pct:.2%} exceeds 3% hard invariant!"
            )
            return False

        return True

    @classmethod
    def check_notional(cls, symbol: str, quantity: float, price: float) -> bool:
        """
        Enforces per-instrument notional cap before order transmission.
        Returns False and logs a CRITICAL if the order exceeds the instrument's limit.
        """
        notional = quantity * price
        limit = cls.MAX_NOTIONAL_PER_ORDER.get(symbol, cls.MAX_NOTIONAL_PER_ORDER["DEFAULT"])
        if notional > limit:
            logger.critical(
                f"NOTIONAL VETO: {symbol} order ${notional:,.0f} exceeds "
                f"hard cap ${limit:,.0f}. Order DENIED."
            )
            return False
        return True
