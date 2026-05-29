"""
src/agent_c_ibkr.py - Agent C IBKR Sovereign Execution Mind
Handles:
- 8-Step Neural Position Sizing Chain (Institutional Standard)
- Institutional-Grade Bracket Orders (Entry, Stop, Profit)
- Financial Advisor (FA) Multi-Account Routing & Allocation
- Advanced Reconnect & Heartbeat Protocols (Agent J Integration)
- Black-Swan Circuit Breakers (Institutional Guard)
"""

import asyncio
import hashlib
import hmac
import logging
import os
import sqlite3
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytz

# NOTE: Do NOT manipulate the event loop at module import time.
# ib_insync's IB() and asyncio.Lock() must only be created inside
# an async context (inside asyncio.run()). All lazy init is deferred
# to _ensure_ib_client() which is only called from async methods.

if TYPE_CHECKING:
    pass

from config import USD_CAD_RATE
from execution_audit import ExecutionAuditLog
from risk_invariants import ORDER_THROTTLER, RiskInvariants
from trading_state import TradingStateManager
from vault import Vault

logger = logging.getLogger(__name__)

# ORDER TYPE REGISTRY


class OrderUrgency:
    HIGH = "HIGH"  # Market Fill
    MEDIUM = "MEDIUM"  # Limit Fill (Aggressive)
    LOW = "LOW"  # Limit Fill (Patient)


class AgentC:
    """Compatibility facade for Agent C's IBKR execution layer."""

    def __init__(self, connection: "IBKRConnection | None" = None) -> None:
        self.connection = connection or IBKRConnection()


# BROKER ERROR PROTOCOL


class BrokerErrorProtocol:
    """Agent C Error Handlers (IBKR Codes)."""

    NON_CRITICAL = [2104, 2106, 2158, 2157]
    RETRYABLE = [1100, 1101, 1102, 10167, 10182]
    CRITICAL = [201, 202, 10148, 10197, 321, 322]

    @staticmethod
    def is_critical(code: int) -> bool:
        return code in BrokerErrorProtocol.CRITICAL


# IBKR CONNECTION & ACCOUNT MONITOR


class IBKRConnection:
    """
    Connection Mind.
        Handles Fault-Tolerant Broker Handshakes and FA-Routing.
    """

    def __init__(self, ib_client=None) -> None:
        if ib_client is not None:
            self.ib = ib_client
        else:
            # IB client is created lazily inside async context via _ensure_ib_client()
            # to avoid event loop errors at construction/import time (Python 3.10+).
            self.ib = None
        self._last_heartbeat = datetime.now()
        self._execution_audit = ExecutionAuditLog()
        self._last_trade_time = datetime.fromtimestamp(0)  # 15-Minute Discipline Lock
        self._positions_cache = {}
        self._account_summary = {}
        self.is_reconnecting = False

        # Financial Advisor (FA) support
        self.managed_accounts = []
        self.current_account_id = None
        # "no current event loop" errors when instantiated before asyncio.run().
        self._lock: asyncio.Lock | None = None
        self._qualified_contracts: dict[str, Any] = {}
        self._warm_slots: dict[str, Any] = {}  # Hyper-Sovereign Warm Path
        self._exec_secret = Vault.get("EXEC_SECRET")
        if not self._exec_secret and os.getenv("SOVEREIGN_ALLOW_DEV_EXEC_SECRET", "0") == "1":
            self._exec_secret = "DEV_ONLY_EXEC_SECRET"
            logger.warning(
                "Using development execution secret because SOVEREIGN_ALLOW_DEV_EXEC_SECRET=1."
            )
        # NOTE: _setup_callbacks() is NOT called here — it must be called after
        # the event loop is running (i.e. from an async method or connect()).
        self._callbacks_registered = False

        self._recovered_orders: set[int] = set()
        self._background_tasks: set[asyncio.Task] = set()  # Prevent GC of pending tasks

    def generate_exec_token(self, symbol: str) -> str:
        """Generate a time-limited HMAC token for order authorization."""
        if not self._exec_secret:
            raise RuntimeError("EXEC_SECRET is not configured")
        current_ts = int(time.time()) // 30
        message = f"{symbol}:{current_ts}"
        return hmac.new(self._exec_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _verify_exec_token(self, symbol: str, token: str) -> bool:
        """
        Verify an HMAC execution token. Checks current and previous 30s
        window for clock drift.
        """
        if not self._exec_secret or not token:
            return False
        current_ts = int(time.time()) // 30
        for offset in (0, -1):  # Allow 1 window of clock drift
            message = f"{symbol}:{current_ts + offset}"
            expected = hmac.new(
                self._exec_secret.encode(), message.encode(), hashlib.sha256
            ).hexdigest()
            if hmac.compare_digest(token, expected):
                return True
        return False

    def is_extended_hours(self) -> bool:
        """Determines if current time is outside RTH (9:30 AM - 4:00 PM ET)."""
        tz = pytz.timezone("US/Eastern")
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return True  # Weekend
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return now < market_open or now > market_close

    def is_near_close(self) -> bool:
        """Sovereign Guard: Checks if market is within 5 minutes of close."""
        tz = pytz.timezone("US/Eastern")
        now = datetime.now(tz)
        if now.weekday() >= 5:
            return False  # Weekend is already handled by is_eth
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        time_to_close = (market_close - now).total_seconds()
        return 0 < time_to_close < 300  # 5 minute buffer

    def validate_order_pre_flight(
        self,
        symbol: str,
        direction: str,
        shares: int,
        price: float,
        account_id: str = None,
        is_close: bool = False,
    ) -> tuple[bool, str]:
        """
        Institutional pre-flight validation: TradingState, throttle, notional,
        account, purchasing power, margin.
        """
        try:
            try:
                shares = int(shares)
                price = float(price)
            except (TypeError, ValueError):
                return False, f"INVALID_ORDER: Non-numeric size/price for {symbol}."
            if shares <= 0 or price <= 0:
                return False, f"INVALID_ORDER: Non-positive size/price for {symbol}."

            # 0a. TradingState FSM gate — block new entries if HALTED or REDUCING
            allowed, state_reason = TradingStateManager.allow_order(is_close=is_close)
            if not allowed:
                return False, state_reason

            # 0b. Order rate throttle — prevents runaway loops flooding the API
            if not ORDER_THROTTLER.can_submit():
                return False, "THROTTLE_VETO: Order submission rate exceeded. Standing down."

            # 0c. Per-instrument notional cap
            if not RiskInvariants.check_notional(symbol, shares, price):
                return False, f"NOTIONAL_VETO: {symbol} order exceeds hard dollar cap."

            # 1. Account Alignment
            from config import IBKR_ACCOUNT_ID

            target_acc = account_id or IBKR_ACCOUNT_ID.strip()
            if target_acc and self.ib and target_acc not in self.ib.wrapper.accounts:
                return False, f"ACCOUNT_MISMATCH: Target {target_acc} not found in broker session."

            # 2. Purchasing Power Guard
            nav_cad = self.get_account_value()
            nav_usd = nav_cad / USD_CAD_RATE
            order_value = abs(shares) * price
            if order_value > nav_usd * 2.0:  # Allow 2x margin maximum
                return (
                    False,
                    f"MARGIN_VIOLATION: Order value ${order_value:,.2f} exceeds 2x NAV "
                    f"(USD: ${nav_usd:,.2f} | CAD: ${nav_cad:,.2f}).",
                )

            # 3. Temporal Execution Awareness
            is_eth = self.is_extended_hours()
            if is_eth:
                logger.info(
                    f" ETH MODE: Order for {symbol} detected Post-Market. "
                    "outsideRth will be FORCED."
                )

            # 4. Margin cushion guard
            cushion = self.get_margin_cushion()
            if cushion < 0.10:
                return (
                    False,
                    f"MARGIN_CUSHION_CRITICAL: {cushion:.1%} is below 10% safety threshold.",
                )

            # 5. Market-Close Risk Guard
            if self.is_near_close() and direction == "BUY" and not is_close:
                return (
                    False,
                    f"MARKET_CLOSE_VETO: Refusing new {symbol} position 5 mins before close.",
                )

            return True, "PROCEED"
        except Exception as e:
            return False, f"PRE_FLIGHT_CRASH: {e}"

    def _ensure_ib_client(self) -> bool:
        """Lazily create IB client. Must only be called from within an async context
        (i.e. after asyncio.run() has started the event loop)."""
        if self.ib is not None:
            return True

        # Ensure the lock also exists (created lazily alongside IB client)
        if self._lock is None:
            try:
                self._lock = asyncio.Lock()
            except RuntimeError as e:
                logger.error(
                    f"agent_c_ibkr: cannot create asyncio.Lock — not inside event loop: {e}"
                )
                return False

        try:
            from ib_insync import IB

            self.ib = IB()
            logger.debug("agent_c_ibkr: IB client created successfully.")
            return True
        except Exception as e:
            logger.error(f"agent_c_ibkr: failed to initialize IB client: {e}")
            self.ib = None
            return False

    def _setup_callbacks(self) -> None:
        """Bind IBKR Real-time Events. Must be called AFTER the event loop is running
        and AFTER _ensure_ib_client() has succeeded."""
        if self._callbacks_registered:
            return  # Idempotent guard — don't double-register
        if not self._ensure_ib_client():
            return

        events = [
            ("errorEvent", self._on_error),
            ("positionEvent", self._on_position),
            ("accountSummaryEvent", self._on_account_summary),
            ("orderStatusEvent", self._on_order_status),
            ("execDetailsEvent", self._on_exec_details),
            ("commissionReportEvent", self._on_commission_report),
            ("disconnectedEvent", self._on_disconnect),
        ]

        for event_name, callback in events:
            try:
                getattr(self.ib, event_name).__iadd__(callback)
            except AttributeError:
                logger.debug(f"IBKRConnection: Event '{event_name}' not available on client.")

        self._callbacks_registered = True
        logger.debug("IBKRConnection: Event callbacks registered.")
        # Note: ib_insync handles account subscriptions automatically on connect.
        # Manual reqAccountSummary is not required and causes argument errors.

    def has_pending_order(self, symbol: str) -> bool:
        """Sovereign Order Shield: Checks if an order for this symbol is already active."""
        if not self.ib:
            return False
        try:
            for trade in self.ib.trades():
                if trade.contract.symbol == symbol and trade.orderStatus.status in (
                    "PendingSubmit",
                    "PreSubmitted",
                    "Submitted",
                ):
                    return True
        except Exception as exc:
            logger.warning("IBKR: pending-order check failed for %s: %s", symbol, exc)
            return True
        return False

    def is_connected(self) -> bool:
        if self.ib is None:
            return False
        try:
            return self.ib.isConnected()
        except Exception as exc:
            logger.debug("IBKR: connection status check failed: %s", exc)
            return False

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Any) -> None:
        if BrokerErrorProtocol.is_critical(errorCode):
            logger.error(f"IBKR [CRITICAL ERROR]: {errorCode} - {errorString}")
        elif errorCode not in BrokerErrorProtocol.NON_CRITICAL:
            logger.debug(f"IBKR [INFO]: {errorCode} - {errorString}")

    def _on_disconnect(self) -> None:
        logger.warning("IBKR: Matrix Connection Severed. Initiating Recovery...")
        if hasattr(self, "bus") and self.bus:
            try:
                self.bus.publish_sync(
                    "system.alert",
                    {
                        "type": "BROKER_DISCONNECTED",
                        "source": "AgentC_IBKR",
                        "message": ("IBKR Connection Severed. Please check TWS/Gateway login."),
                    },
                )
            except Exception as exc:
                logger.warning("IBKR: failed to publish disconnect alert: %s", exc)

    def _on_position(self, pos) -> None:
        self._positions_cache[pos.contract.symbol] = pos.position

    def _on_account_summary(self, item) -> None:
        self._account_summary[item.tag] = item.value

    def _on_order_status(self, trade) -> None:
        status = trade.orderStatus.status
        symbol = trade.contract.symbol
        logger.debug(f"IBKR: Order {trade.order.orderId} status: {status}")

        if status in ("Submitted", "PreSubmitted", "PartiallyFilled"):
            if not hasattr(self, "_order_persistence"):
                self._order_persistence = {}

            # Issue: IMPLEMENT: Persistent Order Tracking (SQLite Bridge)
            def _persist_order_status():
                try:
                    db_path = os.path.join("data", "trading.db")
                    if not os.path.exists("data"):
                        os.makedirs("data")
                    conn = sqlite3.connect(db_path, timeout=60.0)
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout = 60000;")
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS persistent_orders ("
                        "orderId INTEGER PRIMARY KEY, symbol TEXT, status TEXT, "
                        "filled REAL, remaining REAL, last_update TEXT)"
                    )
                    conn.execute(
                        "INSERT OR REPLACE INTO persistent_orders "
                        "(orderId, symbol, status, filled, remaining, last_update) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            trade.order.orderId,
                            symbol,
                            status,
                            trade.orderStatus.filled,
                            trade.orderStatus.remaining,
                            time.time_ns(),
                        ),
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.error(f" ORDER PERSISTENCE FAILURE: {e}")

            import threading as _threading

            _threading.Thread(target=_persist_order_status, daemon=True).start()

            self._order_persistence[trade.order.orderId] = {
                "symbol": symbol,
                "status": status,
                "filled": trade.orderStatus.filled,
                "remaining": trade.orderStatus.remaining,
                "last_update": time.time(),
            }

        if status in ["Cancelled", "Inactive"] and trade.contract.symbol:
            # If we were trying to SELL (Exit), increment failure count in brain
            brain = getattr(self, "brain", None)
            if trade.order.action == "SELL" and brain:
                symbol = trade.contract.symbol
                current_fails = brain._exit_failure_counts.get(symbol, 0)
                brain._exit_failure_counts[symbol] = current_fails + 1
                logger.error(
                    f" SHIELD: Exit failure detected for {symbol}. "
                    f"Total Strikes: {current_fails + 1}"
                )

                # Autonomous Post-Mortem (Zero-Sync background write)
                reason = str(trade.log[-1].message) if trade.log else "UNKNOWN REASON"

                def _write_post_mortem():
                    try:
                        import os
                        import sqlite3

                        db_path = os.path.join("data", "trading.db")
                        if not os.path.exists("data"):
                            os.makedirs("data")
                        conn = sqlite3.connect(db_path, timeout=60.0)
                        conn.execute("PRAGMA journal_mode=WAL;")
                        conn.execute("PRAGMA busy_timeout = 60000;")
                        conn.execute(
                            "CREATE TABLE IF NOT EXISTS failure_post_mortem "
                            "(timestamp TEXT, symbol TEXT, action TEXT, "
                            "status TEXT, reason TEXT)"
                        )
                        conn.execute(
                            "INSERT INTO failure_post_mortem "
                            "(timestamp, symbol, action, status, reason) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (
                                time.time_ns(),
                                symbol,
                                trade.order.action,
                                status,
                                reason,
                            ),
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f" POST-MORTEM FAILURE: {e}")

                # Push to background thread to prevent event loop jitter
                import threading as _threading
                _threading.Thread(target=_write_post_mortem, daemon=True).start()
                logger.info(f" POST-MORTEM: Signal {symbol} failure recorded: {reason}")

    def _on_exec_details(self, trade, fill) -> None:
        """Callback for execution details. Synchronizes actual fill price with Sovereign Mirror."""
        symbol = trade.contract.symbol
        side = fill.execution.side
        qty = fill.execution.shares
        price = fill.execution.avgPrice
        order_id = str(trade.order.orderId)
        parent_id = str(trade.order.parentId)

        logger.info(
            f" IBKR EXECUTION: {symbol} {side} {qty} @ ${price:.2f} "
            f"(Order: {order_id}, Parent: {parent_id})"
        )

        if hasattr(self, "brain") and self.brain:
            for p in self.brain.positions:
                # Match by trade_id (parent) or if this order's parent is our trade_id
                if p.symbol == symbol and (
                    p.trade_id == order_id
                    or p.trade_id == parent_id
                    or f"ADOPTED-{order_id}" in p.trade_id
                    or f"ADOPTED-{parent_id}" in p.trade_id
                ):
                    # If this is an entry (side matches position side)
                    is_long_entry = side == "BOT" and p.qty > 0
                    is_short_entry = side == "SLD" and p.qty < 0

                    if is_long_entry or is_short_entry:
                        old_price = p.entry_price
                        p.entry_price = float(price)
                        # Capture actual slippage
                        p.slippage_cost = abs(p.entry_price - old_price) * abs(p.qty)
                        logger.warning(
                            f" MIRROR ALIGN [{symbol}]: Entry price updated to "
                            f"actual fill ${price:.2f} (Slippage: ${p.slippage_cost:.2f})"
                        )
                    else:
                        # This is likely an exit (Stop Loss or Take Profit)
                        # We don't update entry_price on exit, but we can log the exit slippage
                        logger.info(
                            f" MIRROR ALIGN [{symbol}]: Exit execution detected for {p.trade_id}."
                        )
                    break

    def _on_commission_report(self, trade, fill, report) -> None:
        """Callback for commission reports. Updates the true cost basis of the position."""
        symbol = trade.contract.symbol
        comm = report.commission
        order_id = str(trade.order.orderId)
        parent_id = str(trade.order.parentId)

        logger.info(
            f" IBKR COMMISSION: {symbol} | ${comm:.2f} {report.currency} "
            f"(Order: {order_id}, Parent: {parent_id})"
        )

        if hasattr(self, "brain") and self.brain:
            for p in self.brain.positions:
                if p.symbol == symbol and (
                    p.trade_id == order_id
                    or p.trade_id == parent_id
                    or f"ADOPTED-{order_id}" in p.trade_id
                    or f"ADOPTED-{parent_id}" in p.trade_id
                ):
                    p.commission_cost += float(comm)
                    logger.debug(
                        f" COST ALIGN [{symbol}]: Accumulated commission: ${p.commission_cost:.2f}"
                    )
                    break

    async def ensure_connection(self) -> bool:
        """Handshake with MindGhost (Agent J) for resilient infra."""
        if not self.is_connected() and not self.is_reconnecting:
            logger.warning("IBKR: Connection offline. Requesting infrastructure heal...")
            return False

        # Register callbacks now that we're inside the running event loop
        # (safe to call multiple times — idempotent guard inside _setup_callbacks)
        if not self._callbacks_registered:
            self._setup_callbacks()

        if self.is_connected() and not self._recovered_orders:
            _t = asyncio.create_task(self.recover_orphaned_orders())
            self._background_tasks.add(_t)
            _t.add_done_callback(self._background_tasks.discard)

        return True

    async def recover_orphaned_orders(self) -> None:
        """
        Scans SQLite for orders that were 'In-Flight' during a crash.
        Cross-references with the broker to re-bind or alert.
        """
        if not self.is_connected():
            return

        logger.info("IBKR: Initiating Orphaned Order Recovery...")
        try:
            import os
            import sqlite3

            db_path = os.path.join("data", "trading.db")
            if not os.path.exists(db_path):
                return

            conn = sqlite3.connect(db_path, timeout=60.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout = 60000;")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT orderId, symbol, status FROM persistent_orders "
                    "WHERE status NOT IN ('Filled', 'Cancelled', 'Inactive')"
                )
                orphans = cursor.fetchall()
            finally:
                conn.close()

            if not orphans:
                logger.info("IBKR: No orphaned orders found in local cache.")
                return

            # Fetch open orders from broker for cross-ref
            open_trades = await self.ib.reqAllOpenOrdersAsync()
            broker_order_ids = {t.order.orderId for t in open_trades}

            for oid, sym, status in orphans:
                if oid in broker_order_ids:
                    logger.warning(
                        f" RECOVERY: Found live orphan {oid} for {sym}. Re-binding to tracking."
                    )
                else:
                    logger.error(
                        f" CRITICAL: Order {oid} ({sym}) lost from broker! "
                        f"Status was {status}. Manual audit required."
                    )
                self._recovered_orders.add(oid)

        except Exception as e:
            logger.error(f"IBKR Recovery Error: {e}")

    def get_account_value(self) -> float:
        """Returns NAV from the real-time cache (No API Polling).

        CRITICAL IMPLEMENT: Returns 0.0 (not fallback capital) when IBKR is offline.
        A return of 0.0 will cause the sizer to produce 0 shares, which is safe.
        Returning STARTING_CAPITAL_CAD when offline was causing the sizer to
        calculate positions based on fake capital, resulting in 1000+ share orders.
        """
        if not self.is_connected():
            logger.warning(
                "IBKR: get_account_value() called while OFFLINE. "
                "Returning 0 to block sizer. Will retry once connected."
            )
            return 0.0
        try:
            # 1. Check the event-driven cache first (Updated by _on_account_summary)
            val = self._account_summary.get("NetLiquidation")
            if val is not None:
                return float(val)

            # 2. Fallback to active session values if cache is cold
            acc_vals = self.ib.accountValues()
            liq_vals = [float(item.value) for item in acc_vals if item.tag == "NetLiquidation"]
            if liq_vals:
                val = max(liq_vals)
                self._account_summary["NetLiquidation"] = val
                return val

            logger.warning("IBKR: NAV cache cold. Returning 0 to block sizer until connected.")
            return 0.0
        except Exception as e:
            logger.error(f"IBKR: NAV Cache Retrieval failed: {e}")
            return 0.0

    def get_margin_cushion(self) -> float:
        """
        Sovereign Shield: Returns the margin cushion as a percentage (0.0 to 1.0).
        (EquityWithLoanValue - MaintMarginReq) / EquityWithLoanValue
        """
        try:
            val = self._account_summary.get("EquityWithLoanValue", 0.0)
            maint = self._account_summary.get("MaintMarginReq", 0.0)
            if not val or float(val) == 0:
                return 1.0  # Assume safe if no data to prevent lockouts

            cushion = (float(val) - float(maint)) / float(val)
            return max(0.0, cushion)
        except Exception as e:
            logger.error(f"IBKR Shield: Failed to calculate margin cushion: {e}")
            return 1.0

    def round_to_tick(self, price: float, tick_size: float = 0.01) -> float:
        """Round price to the nearest broker tick size."""
        return round(round(price / tick_size) * tick_size, 4)

    async def warm_up_contracts(self, symbols: list[str]) -> None:
        """
        Pre-qualifies contracts into the local cache to achieve < 50ms order firing.
        """
        if not self.is_connected():
            return

        from ib_insync import Stock

        logger.info(f"IBKR: Initiating Neural Warmup for {len(symbols)} symbols...")

        for symbol in symbols:
            try:
                if symbol in self._qualified_contracts:
                    continue
                from ib_insync import Crypto, Option, Stock

                # 1. Crypto Detection
                is_crypto = symbol.upper() in ["BTC", "ETH", "LTC", "BCH", "DOGE", "SHIB"]

                # 2. Option Detection (OCC Format: SYMBOL YYMMDD C/P Strike)
                # Example: SPY   240621C00500000
                is_option = (
                    len(symbol) >= 15
                    and any(c.isdigit() for c in symbol)
                    and ("C" in symbol or "P" in symbol)
                )

                if is_crypto:
                    contract = Crypto(symbol, "PAXOS", "USD")
                elif is_option:
                    # Resolve Option components for IBKR compatibility
                    # For simple string-based options, we can often just pass the symbol to qualify
                    contract = Option(symbol, "SMART", "USD")
                else:
                    contract = Stock(symbol, "SMART", "USD")

                qualified = await self.ib.qualifyContractsAsync(contract)
                if qualified:
                    self._qualified_contracts[symbol] = qualified[0]
                    logger.debug(
                        f"IBKR [Warmup]: {symbol} ({'Crypto' if is_crypto else 'Stock'}) cached."
                    )
            except Exception as e:
                logger.warning(f"IBKR [Warmup]: Failed to cache {symbol}: {e}")

        logger.info("✓ Neural Warmup: Institutional contract cache synchronized.")

    async def place_bracket_order(
        self,
        symbol: str,
        direction: str,
        shares: int,
        limit_price: float,
        stop_loss: float,
        take_profit: float,
        urgency: str = "LOW",
        **kwargs,  # Added for Ghost Expansion metadata
    ) -> list[int]:
        """
        Place a Bracket Order (Entry + Stop + Profit).
        Now includes SE-11 Ghost Expansion for Stop-Run Protection.
        """
        if kwargs.get("execution_mode") == "GHOST_EXPANSION":
            stop_mult = kwargs.get("stop_multiplier", 1.35)
            size_mult = kwargs.get("size_multiplier", 0.75)

            original_risk = abs(limit_price - stop_loss)
            new_stop_loss = (
                limit_price - (original_risk * stop_mult)
                if direction == "BUY"
                else limit_price + (original_risk * stop_mult)
            )
            new_shares = max(1, int(round(shares * size_mult)))

            logger.info(
                f" GHOST EXPANSION ACTIVE: Scaling {shares} -> {new_shares} | "
                f"Expanding Stop: {stop_loss:.2f} -> {new_stop_loss:.2f}"
            )
            shares = new_shares
            stop_loss = new_stop_loss

        # The caller must provide an exec_token generated by IBKRConnection.generate_exec_token()
        exec_token = kwargs.get("exec_token", "")
        if not self._verify_exec_token(symbol, exec_token):
            logger.critical(
                f"UNAUTHORIZED EXECUTION ATTEMPT for {symbol}! "
                "Invalid or missing exec_token. REJECTING ORDER."
            )
            return []

        try:
            shares = int(shares)
        except (TypeError, ValueError):
            logger.error("IBKR: Invalid bracket share quantity for %s: %r", symbol, shares)
            return []
        if shares <= 0:
            logger.warning("IBKR: Refusing non-positive bracket size for %s: %s", symbol, shares)
            return []

        # Reduced from 30s to 1s to allow Scalping/HFT while preventing API flooding
        # EMERGENCY urgency (stop-loss / VETO exits) always bypasses this throttle.
        wait_seconds = (datetime.now() - self._last_trade_time).total_seconds()
        if wait_seconds < 1.0 and urgency != "EMERGENCY":
            logger.warning(
                f" DISCIPLINE THROTTLE: Trade for {symbol} suppressed. "
                f"Only {wait_seconds:.1f}s elapsed."
            )
            return []

        if self.is_near_close():
            logger.warning(
                f" MARKET CLOSE GUARD: Order for {symbol} rejected (within 5m of close)."
            )
            return []

        if not self.is_connected():
            from config import FORCED_PAPER_MODE

            if FORCED_PAPER_MODE:
                logger.info(
                    f"IBKR [SIM]: Bracket {direction} {shares} {symbol} @ "
                    f"${limit_price} (SL: {stop_loss}, TP: {take_profit})"
                )
                self._last_trade_time = datetime.now()  # Update even in sim
                return [int(time.time()), int(time.time()) + 1, int(time.time()) + 2]
            logger.error(f"IBKR: Offline. Cannot place bracket order for {symbol}.")
            return []

        # Ensure lock exists (lazy-initialized inside async context)
        if self._lock is None:
            self._ensure_ib_client()
        _lock = self._lock or asyncio.Lock()
        async with _lock:  # Ensure serial access to IB client socket
            try:
                # Use cached contract if available (Neural Warmup)
                from ib_insync import LimitOrder, Stock, StopLimitOrder

                if symbol in self._qualified_contracts:
                    contract = self._qualified_contracts[symbol]
                else:
                    contract = Stock(symbol, "SMART", "USD")
                    await self.ib.qualifyContractsAsync(contract)

                # Issue: IMPLEMENT: Limit Price Bias Guard
                # If the spread is wider than 0.5%, use the actual Bid/Ask
                # instead of Mid to ensure fill.
                # Use the brain's real-time tick cache
                bid = self.brain.last_tick_bids.get(symbol, 0.0)
                ask = self.brain.last_tick_asks.get(symbol, 0.0)

                if bid > 0 and ask > 0:
                    if (ask - bid) / bid > 0.005:
                        limit_price = ask if direction == "BUY" else bid
                        logger.info(
                            f"IBKR: Wide spread detected for {symbol}. "
                            f"Overriding Mid with {direction} side: ${limit_price:.2f}"
                        )

                # Tick-size rounding
                lmt = self.round_to_tick(limit_price)
                sl = self.round_to_tick(stop_loss)
                tp = self.round_to_tick(take_profit)

                # 1. Entry Order
                # Enhancement: Force tif=DAY on bracket orders (paper mode overrides GTC -> Error 10349)
                order_tif = "DAY"
                parent = LimitOrder(direction, shares, lmt)
                parent.orderId = self.ib.client.getReqId()
                parent.transmit = False
                parent.overridePercentageConstraints = True
                parent.tif = order_tif

                # Replaced Stop-Market with Stop-Limit ('Recovery Limit')
                # A 2% buffer ensures fill in fast markets while capping
                # slippage at a tolerable level.
                opp_direction = "SELL" if direction == "BUY" else "BUY"
                sl_buffer = 0.02
                sl_limit = (
                    self.round_to_tick(sl * (1 - sl_buffer))
                    if opp_direction == "SELL"
                    else self.round_to_tick(sl * (1 + sl_buffer))
                )

                sl_order = StopLimitOrder(opp_direction, shares, sl_limit, sl)
                sl_order.parentId = parent.orderId
                sl_order.transmit = False
                sl_order.overridePercentageConstraints = True
                sl_order.tif = order_tif

                # 3. Take Profit Order
                tp_order = LimitOrder(opp_direction, shares, tp)
                tp_order.parentId = parent.orderId
                tp_order.transmit = True  # Final order in bracket transmits the entire group
                tp_order.overridePercentageConstraints = True
                tp_order.tif = order_tif

                ids = []
                # Resolve the 'Multi-Account Pillage' issue where empty IBKR_ACCOUNT_ID
                # could lead to unintended execution on multiple accounts.
                from config import IBKR_ACCOUNT_ID

                target_acc = IBKR_ACCOUNT_ID.strip()

                if not target_acc:
                    if self.ib.wrapper.accounts:
                        target_acc = self.ib.wrapper.accounts[0]  # Default to first account
                        logger.info(
                            f"IBKR: No account specified. Defaulting to PRME account: {target_acc}"
                        )
                    else:
                        target_acc = None  # Let IBKR handle default if possible

                target_accounts = [target_acc] if target_acc else [None]

                for i, acc in enumerate(target_accounts):
                    # Clone orders for account targets (Prevents ID collision)
                    p_entry = LimitOrder(direction, shares, lmt)
                    p_entry.orderId = self.ib.client.getReqId()
                    p_entry.transmit = False

                    sl_buff = 0.02
                    sl_lmt = (
                        self.round_to_tick(sl * (1 - sl_buff))
                        if opp_direction == "SELL"
                        else self.round_to_tick(sl * (1 + sl_buff))
                    )
                    sl_o = StopLimitOrder(opp_direction, shares, sl_lmt, sl)
                    sl_o.parentId = p_entry.orderId
                    sl_o.transmit = False

                    tp_o = LimitOrder(opp_direction, shares, tp)
                    tp_o.parentId = p_entry.orderId
                    tp_o.transmit = True  # Finalizes bracket

                    # Set account target
                    for o in [p_entry, sl_o, tp_o]:
                        if acc:
                            o.account = acc
                        trade = self.ib.placeOrder(contract, o)
                        if i == 0:
                            ids.append(trade.order.orderId)

                logger.info(
                    f"IBKR: Sovereign Bracket BROADCAST for {symbol} | "
                    f"Accounts: {len(target_accounts)} | Entry: {lmt}"
                )
                return ids

            except Exception as e:
                logger.error(f"IBKR Bracket Failure for {symbol}: {e}")
                return []

    def _persist_execution(self, symbol: str, order_type: str, details: dict):
        """Write a persistent execution log entry for audit trail and manual recovery."""
        try:
            audit_record = self._execution_audit.append(
                event="ORDER_INTENT",
                symbol=symbol,
                side=str(details.get("dir", details.get("direction", "UNKNOWN"))),
                quantity=float(details.get("shares", details.get("quantity", 0)) or 0),
                order_type=order_type,
                details=details,
            )
            log_file = "data/execution_persistence.jsonl"
            import json
            import os

            os.makedirs("data", exist_ok=True)
            entry = {
                "timestamp": time.time_ns(),
                "symbol": symbol,
                "type": order_type,
                "details": details,
                "audit_hash": audit_record.get("hash"),
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"IBKR: Failed to persist execution log: {e}")

    async def place_order(
        self,
        symbol: str,
        direction: str,
        shares: int,
        order_type: str = "LMT",
        limit_price: float = 0.0,
        urgency: str = "LOW",
        tif: str = "DAY",
        **kwargs,
    ) -> int | None:
        """
        Institutional Single Order Routing.
        """
        exec_token = kwargs.get("exec_token", "")
        if not self._verify_exec_token(symbol, exec_token):
            logger.critical(
                f"UNAUTHORIZED EXECUTION ATTEMPT for '{symbol}'! "
                "Invalid or missing exec_token. REJECTING ORDER."
            )
            return None

        try:
            shares = int(shares)
        except (TypeError, ValueError):
            logger.error("IBKR: Invalid share quantity for %s: %r", symbol, shares)
            return None
        if shares <= 0:
            logger.warning("IBKR: Refusing non-positive order size for %s: %s", symbol, shares)
            return None

        wait_seconds = (datetime.now() - self._last_trade_time).total_seconds()
        if wait_seconds < 1.0 and urgency != "EMERGENCY":
            logger.warning(f" DISCIPLINE THROTTLE: Order for {symbol} suppressed.")
            return None

        if not self.is_connected():
            from config import FORCED_PAPER_MODE

            if FORCED_PAPER_MODE:
                logger.info(f"IBKR [SIM]: Routing {direction} {shares} {symbol} (Mode: {urgency})")
                return int(time.time())
            logger.error(f"IBKR: Offline. Cannot place Single order for {symbol}.")
            return None

        # Ensure lock exists (lazy-initialized inside async context)
        if self._lock is None:
            self._ensure_ib_client()
        _lock = self._lock or asyncio.Lock()
        async with _lock:  # Ensure serial access to IB client socket
            self._persist_execution(
                symbol,
                "SINGLE",
                {"dir": direction, "shares": shares, "px": limit_price, "type": order_type},
            )

            try:
                from ib_insync import Future, LimitOrder, MarketOrder, Stock

                if "=F" in symbol:
                    root = symbol.split("=")[0].upper()
                    if root in ("NQ", "MNQ", "ES", "MES", "RTY", "M2K"):
                        exchange = "GLOBEX"
                    elif root in ("YM", "MYM"):
                        exchange = "ECBOT"
                    elif root in ("GC", "MGC", "SI", "HG"):
                        exchange = "NYMEX" if root in ("SI", "HG") else "COMEX"
                    elif root in ("CL", "BZ"):
                        exchange = "NYMEX"
                    else:
                        exchange = "SMART"
                    contract = Future(root, exchange=exchange, currency="USD")
                else:
                    contract = Stock(symbol, "SMART", "USD")

                await self.ib.qualifyContractsAsync(contract)

                # Tick rounding
                lmt = self.round_to_tick(limit_price)

                # Attempt to modify an existing dormant order for sub-ms priority
                warm_id = await self._execute_via_warm_slot(symbol, direction, shares, limit_price)
                if warm_id:
                    return warm_id

                from config import IBKR_ACCOUNT_ID

                target_acc = IBKR_ACCOUNT_ID.strip()

                if not target_acc:
                    if self.ib.wrapper.accounts:
                        target_acc = self.ib.wrapper.accounts[0]
                        logger.info(
                            f"IBKR: Defaulting to PRIME account for single order: {target_acc}"
                        )
                    else:
                        target_acc = None

                target_accounts = [target_acc] if target_acc else [None]

                primary_id = None
                for i, acc in enumerate(target_accounts):
                    if urgency == "EMERGENCY":
                        o = MarketOrder(direction, shares)
                    elif urgency == "HIGH" or order_type == "MKT":
                        # Replaced MarketOrder with 'Aggressive Limit' to prevent
                        # flash-crash slippage. We use a 1.5% buffer for entries
                        # and exits; if it doesn't fill, we prefer a miss
                        # over a ruinous price.
                        buffer = 0.015
                        price = limit_price
                        if price <= 0.0:
                            # Try to get real-time price from the brain's tick cache
                            if direction == "BUY":
                                price = self.brain.last_tick_asks.get(
                                    symbol, 0.0
                                ) or self.brain.last_tick_prices.get(symbol, 0.0)
                            else:
                                price = self.brain.last_tick_bids.get(
                                    symbol, 0.0
                                ) or self.brain.last_tick_prices.get(symbol, 0.0)

                            # If still 0, try to get from ib.ticker
                            if price <= 0.0:
                                t = self.ib.ticker(contract)
                                if t:
                                    if direction == "BUY":
                                        price = (
                                            t.ask
                                            if t.ask > 0
                                            else t.last
                                            if t.last > 0
                                            else t.close or 0.0
                                        )
                                    else:
                                        price = (
                                            t.bid
                                            if t.bid > 0
                                            else t.last
                                            if t.last > 0
                                            else t.close or 0.0
                                        )

                        if price <= 0.0:
                            # Fallback to MarketOrder if price cannot be resolved
                            o = MarketOrder(direction, shares)
                        else:
                            if direction == "BUY":
                                lmt_buffered = (
                                    self.round_to_tick(lmt * (1 + buffer))
                                    if lmt
                                    else self.round_to_tick(price * (1 + buffer))
                                )
                            else:
                                lmt_buffered = (
                                    self.round_to_tick(lmt * (1 - buffer))
                                    if lmt
                                    else self.round_to_tick(price * (1 - buffer))
                                )

                            o = LimitOrder(direction, shares, lmt_buffered)
                            o.outsideRth = self.is_extended_hours()
                            o.overridePercentageConstraints = True
                    else:
                        o = LimitOrder(direction, shares, lmt)
                        o.outsideRth = self.is_extended_hours()
                        o.overridePercentageConstraints = True

                    o.tif = tif
                    if acc:
                        o.account = acc

                    trade = self.ib.placeOrder(contract, o)
                    if i == 0:
                        primary_id = trade.order.orderId
                        _audit_t = asyncio.create_task(self._audit_execution(trade, symbol, shares))
                        self._background_tasks.add(_audit_t)
                        _audit_t.add_done_callback(self._background_tasks.discard)

                if primary_id is None:
                    logger.error("IBKR: No primary order id returned for %s.", symbol)
                    return None

                self._last_trade_time = datetime.now()  # Update Discipline Lock
                return primary_id

            except Exception as e:
                logger.error(f"IBKR Routing Failure for {symbol}: {e}")
                return None

    async def _maintain_warm_slots(self, symbols: list[str]) -> None:
        """
        Maintains 'Dormant Orders' on the exchange to preserve a 'Warm Path'.
        Modifying an existing order is often faster than submitting a new one.
        """
        if not self.is_connected():
            return


        for symbol in symbols:
            if symbol not in self._warm_slots:
                # SAFETY: Do NOT place live orders for warm slots.
                # and bypass paper-mode leakage.
                self._warm_slots[symbol] = None
                logger.debug(
                    f"IBKR: Warm-Slot tracked internally for {symbol} (no live order placed)"
                )
    async def _execute_via_warm_slot(
        self, symbol: str, direction: str, shares: int, price: float
    ) -> int | None:
        """Executes a trade by MODIFYING an existing dormant order (The Hyper-Sovereign Leap)."""
        if symbol not in self._warm_slots:
            return None

        trade = self._warm_slots[symbol]
        # If warm slot is None (safety mode: no dormant orders placed),
        # fall back to a normal fresh order instead of modifying.
        if trade is None:
            return None
        status = getattr(getattr(trade, "orderStatus", None), "status", "")
        if status in ("Filled", "Cancelled", "Inactive"):
            del self._warm_slots[symbol]
            return None

        rounded_price = self.round_to_tick(price)
        if rounded_price <= 0:
            logger.warning(
                "IBKR: Warm-slot path rejected for %s because execution price is %.4f.",
                symbol,
                price,
            )
            return None

        # Transform the dormant order into the real tiger
        trade.order.action = direction
        trade.order.totalQuantity = shares
        trade.order.lmtPrice = rounded_price
        trade.order.transmit = True

        self.ib.placeOrder(trade.contract, trade.order)
        logger.info(
            f" HYPER-SOVEREIGN: Warm-Slot MODIFICATION executed for {symbol} (Sub-ms path)."
        )

        # Remove from warm-slots so a new one can be pre-loaded
        del self._warm_slots[symbol]
        return trade.order.orderId

    async def _audit_execution(self, trade: Any, symbol: str, shares: int) -> None:
        """
        Institutional Persistent Audit.
        Polls the portfolio every 10s for 60s to ensure Reality Alignment.
        Prevents false-positive shutdowns caused by IBKR sync latency.
        """
        _target_acc = trade.order.account
        for _attempt in range(6):  # Poll for 60s total
            await asyncio.sleep(10)
            if trade.orderStatus.status == "Filled":
                logger.info(f"✓ AUDIT SUCCESS: {symbol} execution verified (Status: Filled).")
                return  # Alignment confirmed

        # If we reach here after 60s, it's a true critical inconsistency
        logger.critical(
            f"IBKR: SILENT EXECUTION FAILURE DETECTED for {symbol}. "
            "Inconsistency persistent after 60s."
        )
        self._last_heartbeat = datetime(1970, 1, 1)  # Poison the heartbeat

    def cancel_order(self, order_id: int) -> bool:
        if not self.is_connected():
            return False
        try:
            orders = self.ib.openOrders()
            for order in orders:
                if order.orderId == order_id:
                    self.ib.cancelOrder(order)
                    return True
            return False
        except Exception as e:
            logger.error(f"IBKR: Cancel failed for {order_id}: {e}")
            return False

    def get_positions(self) -> list[dict]:
        if not self.is_connected():
            return []
        try:
            positions = self.ib.positions()
            return [
                {
                    "symbol": p.contract.symbol,
                    "shares": float(p.position),
                    "avg_cost": float(getattr(p, "avgCost", 0.0)),
                    "account": p.account,
                }
                for p in positions
            ]
        except Exception as exc:
            logger.debug("IBKR: failed to fetch open positions: %s", exc)
            return []


# INSTITUTIONAL 8-STEP SIZING CHAIN


class PositionSizingChain:
    """Agent C: Mathematical Sizer (8-Step Imperial Integration)."""

    def __init__(self) -> None:
        from agent_a import ImpactOracle

        self.impact_oracle = ImpactOracle()

    def calculate(
        self, win_prob: float, r_r_ratio: float, balance: float, **kwargs
    ) -> dict[str, Any]:
        """
        Calculates position size using the 8-Step SETO Paradox.
        """

        def zero_size() -> dict[str, Any]:
            return {
                "shares": 0,
                "step8_shares": 0,
                "position_size": 0,
                "risk_dollars": 0.0,
                "balance_used": balance if "balance" in locals() else 0.0,
                "proposed_value": 0.0,
                "position_value": 0.0,
                "steps": {},
            }

        instrument = kwargs.get("instrument", kwargs.get("symbol", "UNKNOWN"))
        from risk_invariants import RiskInvariants

        _raw_nav = kwargs.get("account_value", balance)

        if _raw_nav <= 0:
            logger.warning(f"Sizer DEBUG: {instrument} received ZERO balance. Sizing will be 0.")

        balance = min(balance, _raw_nav) * 0.99

        kelly_pct = (win_prob - ((1 - win_prob) / r_r_ratio)) / 2.0 if r_r_ratio > 0 else 0
        step1_risk = balance * max(0, kelly_pct)

        from config import CASH_ACCOUNT_MAX_RATIO, RISK_PER_TRADE_PCT, SYSTEM_MAX_RISK

        step2_risk = min(step1_risk, balance * SYSTEM_MAX_RISK)

        step3_risk = min(step2_risk, balance * CASH_ACCOUNT_MAX_RATIO)

        gap_mod = kwargs.get("gap_modifier", 1.0)
        step4_risk = step3_risk * max(0.5, min(1.5, gap_mod))

        regime_mod = kwargs.get("regime_modifier", 1.0)
        if regime_mod <= 0:
            logger.warning(f"Sizer: {instrument} received zero/negative regime modifier. No trade.")
            return zero_size()
        bounded_regime_mod = max(0.1, min(1.5, regime_mod))
        step5_risk = step4_risk * bounded_regime_mod

        fat_tail_mod = 0.82 if win_prob < 0.6 else 1.0
        step6_risk = step5_risk * fat_tail_mod

        # We apply a high 'Safety Floor' (0.8) to bypass the ghost loss memory
        # while keeping the logic dynamic enough for the Phantom Probe monitor.
        # Safety cap: drawdown/loss modifiers can only REDUCE size (max 1.0), never increase it.
        # Floor at 0.5 to prevent total paralysis on a brief losing streak.
        dd_mod = min(max(kwargs.get("drawdown_modifier", 1.0), 0.5), 1.0)
        loss_mod = min(max(kwargs.get("loss_modifier", 1.0), 0.5), 1.0)

        base_risk_limit = balance * RISK_PER_TRADE_PCT if RISK_PER_TRADE_PCT > 0 else balance * 0.01
        self_risk_limit = base_risk_limit * max(1.0, bounded_regime_mod)

        # If Kelly says 0, but the Quorum approved, force a small experimental 'Mini-Risk'
        min_viable_risk = 2.0 if balance < 1000 else balance * 0.001
        step7_final_risk = min(max(step6_risk, min_viable_risk), self_risk_limit)

        # Apply the Sovereign safety multipliers to the final dollar risk
        step7_final_risk *= dd_mod * loss_mod

        # FINAL FLOOR: Ensure risk covers at least the commission + slippage buffer
        if balance < 1000:
            step7_final_risk = max(step7_final_risk, 2.0)

        try:
            price = float(kwargs.get("entry_price", kwargs.get("price", 1.0)))
            stop = float(kwargs.get("stop_price", price * 0.99))
            spread = max(0.0, float(kwargs.get("spread", 0.0)))
        except (TypeError, ValueError):
            logger.error(f"Sizer: [INPUT_VETO] {instrument} received invalid price inputs.")
            return zero_size()
        if price <= 0:
            logger.error(f"Sizer: [INPUT_VETO] {instrument} received non-positive price.")
            return zero_size()

        # Real risk per share must include the spread we cross to enter.
        # For long: Entry is ASK, Stop is BID. Diff = (Ask - Bid) + (Bid - Stop) = Ask - Stop.
        # But we also factor in a 'Slippage Buffer' (0.5 ticks) for fast markets.
        risk_per_share = abs(price - stop) + (spread)

        # REAL R:R (Friction-Aware)
        target = kwargs.get("target_price", price * 1.01)
        real_reward = abs(target - price) - (spread)
        if risk_per_share > 0:
            real_rr = real_reward / risk_per_share
            if real_rr < 1.0:
                logger.warning(
                    f"Sizer: [FRICTION VETO] {instrument} R:R with spread is only "
                    f"{real_rr:.2f} (Target Reward ${real_reward:.2f} < "
                    f"Risk ${risk_per_share:.2f})."
                )
                # We don't return 0 here yet, Phase 7 might still approve if high win_prob.

        if risk_per_share < (price * 0.0001):
            # If risk is too tight (< 0.01% of price), the geometry is invalid for HFT.
            logger.error(
                f"Sizer: [GEOMETRY_VETO] {instrument} risk (${risk_per_share:.4f}) "
                f"is too tight for price ${price:.2f}. Rejecting."
            )
            return zero_size()

        if step7_final_risk <= 0 or step6_risk <= 0:
            logger.warning(
                f"Sizer: Risk math resulted in zero exposure for {instrument}. Quashing trade."
            )
            return zero_size()

        step8_shares = int(round(step7_final_risk / risk_per_share)) if risk_per_share > 0 else 0

        # This prevents forced over-leverage on micro-accounts ($500 etc.)
        min_trade_value = balance * 0.02  # 2% of NAV = $10 on $500 account
        if (
            step8_shares >= 0
            and (step8_shares * price) < min_trade_value
            and price > 0
            and step7_final_risk > 0
        ):
            step8_shares = max(1, int(round(min_trade_value / price)))

        # Final Position Value Guard (10% max of NAV per trade)
        # Cap this by the hard dollar limit from RiskInvariants
        hard_cap = RiskInvariants.MAX_NOTIONAL_PER_ORDER.get(
            instrument, RiskInvariants.MAX_NOTIONAL_PER_ORDER["DEFAULT"]
        )
        max_notional = min(balance * 0.10, hard_cap)

        if step8_shares > 0 and (step8_shares * price) > max_notional:
            logger.warning(
                f"Sizer: Capping {instrument} at max notional "
                f"(${max_notional:,.2f}) because math was too aggressive."
            )
            step8_shares = max(1, int(max_notional / price))

        if step8_shares == 0 and step7_final_risk > (price * 0.5):
            # If the risk budget allows for at least 0.5 shares, we force 1 share
            # This allows $500 accounts to take positions where price is $100 and risk is $10
            step8_shares = 1
            logger.info(
                f"Sizer: [SMALL_ACC_FIX] Forcing 1 share for {instrument} despite risk rounding."
            )

        ohlcv = kwargs.get("ohlcv_df")

        if ohlcv is not None and len(ohlcv) < 50 and not kwargs.get("is_probe"):
            logger.warning(
                f"Sizer: [IPO_GUARD] {instrument} has < 50 bars of history. "
                "Rejecting for low-liquidity/high-volatility risk."
            )
            return zero_size()

        if ohlcv is not None and step8_shares > 0:
            est_slippage = self.impact_oracle.estimate_impact(instrument, step8_shares, ohlcv)
            # If slippage eats more than 15% of the expected profit, we downsize
            expected_profit_pct = abs(kwargs.get("target_price", price * 1.02) - price) / price
            if est_slippage > (expected_profit_pct * 0.15):
                logger.warning(
                    f"Sizer: [IMPACT_GUARD] {instrument} slippage {est_slippage:.2%} "
                    "> 15% of reward. Downsizing 50% for safety."
                )
                step8_shares = max(1, int(round(step8_shares * 0.5)))
        elif step8_shares > 0 and not kwargs.get("is_probe"):
            logger.warning(
                f"Sizer: [IMPACT_GAP] No OHLCV data for {instrument} impact estimation. "
                "Applying 30% blind downsizing."
            )
            step8_shares = max(1, int(round(step8_shares * 0.7)))

        # If the expected profit is less than round-trip commission, the trade is a guaranteed loss.
        from config import COMMISSION_PER_ROUND_TRIP

        expected_reward = (
            step8_shares * abs(price - kwargs.get("target_price", price * 1.03))
            if step8_shares > 0
            else 0
        )
        if expected_reward > 0 and expected_reward < COMMISSION_PER_ROUND_TRIP:
            logger.warning(
                f"Sizer: COMMISSION KILL for {instrument}. Expected reward "
                f"${expected_reward:.2f} < commission ${COMMISSION_PER_ROUND_TRIP:.2f}. "
                "Quashing trade."
            )
            return zero_size()

        if not RiskInvariants.audit_trade_parameters(step7_final_risk, balance):
            logger.critical(
                f"Sizer: [INVARIANT VETO] Proposed risk for {instrument} "
                "violates hard safety bounds."
            )
            return zero_size()

        logger.info(
            f"Imperial Sizer: [NAV: ${balance:,.2f}] -> "
            f"[Risk: ${step7_final_risk:,.2f}] -> [Shares: {step8_shares}]"
        )

        return {
            "shares": step8_shares if step8_shares > 0 else 0,
            "step8_shares": step8_shares if step8_shares > 0 else 0,  # Legacy key for Coordinator
            "position_size": step8_shares if step8_shares > 0 else 0,
            "risk_dollars": step7_final_risk,
            "balance_used": balance,
            "proposed_value": step8_shares * price,
            "position_value": step8_shares * price,  # Legacy key for Coordinator
            "steps": {"kelly": step1_risk, "regime": step5_risk, "final": step7_final_risk},
            "total_multiplier": (dd_mod * loss_mod),
        }


class VIXProtocol:
    def get_modifier(self, vix: float) -> float:
        if vix > 35:
            return 0.25
        if vix > 25:
            return 0.50
        return 1.0

    def evaluate_proposal(
        self, context: dict[str, Any], agent_name: str = "Agent_F"
    ) -> dict[str, Any]:
        """Agent F: VIX/Volatility Guard Vote."""
        vix = context.get("vix", getattr(self, "_last_vix", 20.0))
        self._last_vix = vix

        # Track 30-day moving average (placeholder for actual rolling calc)
        # In a real system, this would be fed from the database.
        # For now, we use a smoothing factor to adapt the 'Safe' threshold.
        current_ma = getattr(self, "_vix_ma", 20.0)
        self._vix_ma = (current_ma * 0.95) + (vix * 0.05)

        # Safe threshold is now MA + 25% buffer, capped at 30
        safe_threshold = min(30.0, self._vix_ma * 1.25)

        v_low = vix < safe_threshold
        return {
            "agent": agent_name,
            "vote": "YES" if v_low else "NO",
            "confidence": 0.8 if v_low else 0.4,
            "reason": f"VIX at {vix:.2f} (Threshold: {safe_threshold:.2f})"
            if v_low
            else (f"VIX Spike {vix:.2f} (Dynamic Threshold {safe_threshold:.2f} Exceeded)"),
            "risk_flag": str(not v_low),
        }

    def monitor_intraday(self, current: float, high: float, low: float) -> str:
        """The Sovereign Intraday Circuit Breaker (Nuclear Option)."""
        # If VIX sustains above 45.0, initiate whole-portfolio liquidation
        if current > 45.0:
            return "CLOSE at market"
        return "CONTINUE"


SECTOR_MAP = {
    "AAPL": "TECH", "MSFT": "TECH", "GOOGL": "TECH", "GOOG": "TECH",
    "AMZN": "TECH", "META": "TECH", "NVDA": "TECH", "TSLA": "TECH",
    "AMD": "TECH", "INTC": "TECH", "CRM": "TECH", "ORCL": "TECH",
    "ADBE": "TECH", "AVGO": "TECH", "QCOM": "TECH", "TXN": "TECH",
    "NFLX": "TECH", "UBER": "TECH", "ABNB": "TECH", "PYPL": "TECH",
    "JPM": "FIN", "BAC": "FIN", "WFC": "FIN", "GS": "FIN",
    "MS": "FIN", "C": "FIN", "BLK": "FIN", "AXP": "FIN",
    "V": "FIN", "MA": "FIN", "COF": "FIN", "SPGI": "FIN",
    "JNJ": "HEALTH", "PFE": "HEALTH", "UNH": "HEALTH", "ABBV": "HEALTH",
    "MRK": "HEALTH", "LLY": "HEALTH", "TMO": "HEALTH", "ABT": "HEALTH",
    "DHR": "HEALTH", "BMY": "HEALTH", "AMGN": "HEALTH", "GILD": "HEALTH",
    "XOM": "ENERGY", "CVX": "ENERGY", "COP": "ENERGY", "EOG": "ENERGY",
    "SLB": "ENERGY", "OXY": "ENERGY", "MPC": "ENERGY", "VLO": "ENERGY",
    "WMT": "CONS", "COST": "CONS", "HD": "CONS", "LOW": "CONS",
    "TGT": "CONS", "PG": "CONS", "KO": "CONS", "PEP": "CONS",
    "MCD": "CONS", "SBUX": "CONS", "NKE": "CONS", "TJX": "CONS",
    "GE": "IND", "CAT": "IND", "HON": "IND", "UPS": "IND",
    "BA": "IND", "RTX": "IND", "LMT": "IND", "DE": "IND",
    "MMM": "IND", "CSX": "IND", "UNP": "IND", "FDX": "IND",
    "SPY": "BROAD", "QQQ": "BROAD", "IWM": "BROAD", "VTI": "BROAD",
    "DIA": "BROAD", "VOO": "BROAD", "IVV": "BROAD", "VTV": "BROAD",
}


def _get_sector(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), symbol.upper())


class CorrelationCascade:
    def check_exposure(self, symbol: str, positions: list[Any], equity: float) -> bool:
        # Prevent more than 30% exposure in a single sector using real sector map
        sector = _get_sector(symbol)
        sector_exposure = sum(
            abs(p.qty * p.entry_price) for p in positions if _get_sector(p.symbol) == sector
        )
        if sector_exposure / max(equity, 1) > 0.35:
            return False
        return True


class BlackSwanProtocol:
    def check(self, vix: float, drawdown_pct: float) -> str:
        return "FREEZE" if vix > 55 or drawdown_pct > 0.12 else "NORMAL"


class PortfolioGuard:
    """Agent C: Imperial Safety Valve."""

    def enforce_cash_reserve(self, balance: float, total_position_value: float) -> bool:
        # 20% Mandatory Cash Reserve
        return total_position_value <= (balance * 0.80)

    def evaluate_proposal(
        self, context: dict[str, Any], agent_name: str = "Agent_C"
    ) -> dict[str, Any]:
        """Evaluate portfolio-level risk and return a compliance vote."""
        balance = context.get("balance") or context.get("account_value", 0.0)
        total_p_val = context.get("total_position_value", 0.0)
        proposed_val = context.get("proposed_value") or context.get("new_position_value", 0.0)

        is_compliant = (total_p_val + proposed_val) <= (balance * 0.85)  # Allowing 15% buffer

        return {
            "agent": agent_name,
            "vote": "YES" if is_compliant else "NO",
            "confidence": 1.0,
            "reason": "Portfolio complies with Cash Reserve"
            if is_compliant
            else (
                f"CASH_RESERVE_VETO: Total exposure would exceed 85% NAV "
                f"(${(total_p_val + proposed_val):.2f} > ${(balance * 0.85):.2f})"
            ),
            "timestamp": time.time_ns(),
        }
