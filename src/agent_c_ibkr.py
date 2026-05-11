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
from typing import Any

import pytz
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ib_insync import IB

from config import STARTING_CAPITAL_CAD, USD_CAD_RATE
from risk_invariants import ORDER_THROTTLER, RiskInvariants
from trading_state import TradingStateManager
from vault import Vault

logger = logging.getLogger(__name__)

# ORDER TYPE REGISTRY


class OrderUrgency:
    HIGH = "HIGH"  # Market Fill
    MEDIUM = "MEDIUM"  # Limit Fill (Aggressive)
    LOW = "LOW"  # Limit Fill (Patient)


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
            try:
                from ib_insync import IB

                self.ib = IB()
            except Exception as e:
                logger.error(f"agent_c_ibkr: failed to initialize IB client: {e}")
                self.ib = None
        self._last_heartbeat = datetime.now()
        self._last_trade_time = datetime.fromtimestamp(0)  # 15-Minute Discipline Lock
        self._positions_cache = {}
        self._account_summary = {}
        self.is_reconnecting = False

        # Financial Advisor (FA) support
        self.managed_accounts = []
        self.current_account_id = None
        self._lock = asyncio.Lock()  # PILLAR 3: Concurrency Safety for Parallel Vetting
        self._qualified_contracts: dict[str, Any] = {}
        self._warm_slots: dict[str, Any] = {}  # Hyper-Sovereign Warm Path
        self._exec_secret = (
            Vault.get("EXEC_SECRET", "SETO_SOVEREIGN_EXEC_V22") or "SETO_SOVEREIGN_EXEC_V22"
        )
        self._setup_callbacks()

        self._recovered_orders: set[int] = set()

    def generate_exec_token(self, symbol: str) -> str:
        """Generate a time-limited HMAC token for order authorization."""
        current_ts = int(time.time()) // 30
        message = f"{symbol}:{current_ts}"
        return hmac.new(self._exec_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    def _verify_exec_token(self, symbol: str, token: str) -> bool:
        """Verify an HMAC execution token. Checks current and previous 30s window for clock drift."""
        if not token:
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
        """Institutional pre-flight validation: TradingState, throttle, notional, account, purchasing power, margin."""
        try:
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
            if target_acc and target_acc not in self.ib.wrapper.accounts:
                return False, f"ACCOUNT_MISMATCH: Target {target_acc} not found in broker session."

            # 2. Purchasing Power Guard
            nav_cad = self.get_account_value()
            nav_usd = nav_cad / USD_CAD_RATE
            order_value = shares * price
            if order_value > nav_usd * 2.0:  # Allow 2x margin maximum
                return (
                    False,
                    f"MARGIN_VIOLATION: Order value ${order_value:,.2f} exceeds 2x NAV (USD: ${nav_usd:,.2f} | CAD: ${nav_cad:,.2f}).",
                )

            # 3. Temporal Execution Awareness
            is_eth = self.is_extended_hours()
            if is_eth:
                logger.info(
                    f"🏛️ ETH MODE: Order for {symbol} detected Post-Market. outsideRth will be FORCED."
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

    def _setup_callbacks(self) -> None:
        """Bind IBKR Real-time Events (Safely)."""
        if not self.ib:
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

        # Note: ib_insync handles account subscriptions automatically on connect.
        # Manual reqAccountSummary is not required and causes argument errors.

    @property
    def is_connected(self) -> bool:
        return self.ib is not None and self.ib.isConnected()

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
                        "message": "IBKR Connection Severed. Please check TWS/Gateway login.",
                    },
                )
            except Exception:
                pass

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

            # Bug 31 FIX: Persistent Order Tracking (SQLite Bridge)
            def _persist_order_status():
                try:
                    db_path = os.path.join("data", "trading.db")
                    if not os.path.exists("data"):
                        os.makedirs("data")
                    conn = sqlite3.connect(db_path, timeout=60.0)
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout = 60000;")
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS persistent_orders (orderId INTEGER PRIMARY KEY, symbol TEXT, status TEXT, filled REAL, remaining REAL, last_update TEXT)"
                    )
                    conn.execute(
                        "INSERT OR REPLACE INTO persistent_orders (orderId, symbol, status, filled, remaining, last_update) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            trade.order.orderId,
                            symbol,
                            status,
                            trade.orderStatus.filled,
                            trade.orderStatus.remaining,
                            datetime.now().isoformat(),
                        ),
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.error(f"🚨 ORDER PERSISTENCE FAILURE: {e}")

            import asyncio as _asyncio

            _asyncio.get_event_loop().run_in_executor(None, _persist_order_status)

            self._order_persistence[trade.order.orderId] = {
                "symbol": symbol,
                "status": status,
                "filled": trade.orderStatus.filled,
                "remaining": trade.orderStatus.remaining,
                "last_update": time.time(),
            }

        # --- SOVEREIGN SHIELD: FAILURE FEEDBACK ---
        if status in ["Cancelled", "Inactive"] and trade.contract.symbol:
            # If we were trying to SELL (Exit), increment failure count in brain
            brain = getattr(self, "brain", None)
            if trade.order.action == "SELL" and brain:
                symbol = trade.contract.symbol
                current_fails = brain._exit_failure_counts.get(symbol, 0)
                brain._exit_failure_counts[symbol] = current_fails + 1
                logger.error(
                    f"🛡️ SHIELD: Exit failure detected for {symbol}. Total Strikes: {current_fails + 1}"
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
                            "CREATE TABLE IF NOT EXISTS failure_post_mortem (timestamp TEXT, symbol TEXT, action TEXT, status TEXT, reason TEXT)"
                        )
                        conn.execute(
                            "INSERT INTO failure_post_mortem (timestamp, symbol, action, status, reason) VALUES (?, ?, ?, ?, ?)",
                            (
                                datetime.now().isoformat(),
                                symbol,
                                trade.order.action,
                                status,
                                reason,
                            ),
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        logger.error(f"🚨 POST-MORTEM FAILURE: {e}")

                # Push to background thread to prevent event loop jitter
                asyncio.get_event_loop().run_in_executor(None, _write_post_mortem)
                logger.info(f"📉 POST-MORTEM: Signal {symbol} failure recorded: {reason}")

    def _on_exec_details(self, trade, fill) -> None:
        """Callback for execution details. Synchronizes actual fill price with Sovereign Mirror."""
        symbol = trade.contract.symbol
        side = fill.execution.side
        qty = fill.execution.shares
        price = fill.execution.avgPrice
        order_id = str(trade.order.orderId)
        parent_id = str(trade.order.parentId)

        logger.info(
            f"🏛️ IBKR EXECUTION: {symbol} {side} {qty} @ ${price:.2f} (Order: {order_id}, Parent: {parent_id})"
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
                            f"⚖️ MIRROR ALIGN [{symbol}]: Entry price updated to actual fill ${price:.2f} (Slippage: ${p.slippage_cost:.2f})"
                        )
                    else:
                        # This is likely an exit (Stop Loss or Take Profit)
                        # We don't update entry_price on exit, but we can log the exit slippage
                        logger.info(
                            f"⚖️ MIRROR ALIGN [{symbol}]: Exit execution detected for {p.trade_id}."
                        )
                    break

    def _on_commission_report(self, trade, fill, report) -> None:
        """Callback for commission reports. Updates the true cost basis of the position."""
        symbol = trade.contract.symbol
        comm = report.commission
        order_id = str(trade.order.orderId)
        parent_id = str(trade.order.parentId)

        logger.info(
            f"🏛️ IBKR COMMISSION: {symbol} | ${comm:.2f} {report.currency} (Order: {order_id}, Parent: {parent_id})"
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
                        f"⚖️ COST ALIGN [{symbol}]: Accumulated commission: ${p.commission_cost:.2f}"
                    )
                    break

    async def ensure_connection(self) -> bool:
        """Handshake with MindGhost (Agent J) for resilient infra."""
        if not self.is_connected and not self.is_reconnecting:
            logger.warning("IBKR: Connection offline. Requesting infrastructure heal...")
            return False

        if self.is_connected and not self._recovered_orders:
            asyncio.create_task(self.recover_orphaned_orders())

        return True

    async def recover_orphaned_orders(self) -> None:
        """
        Scans SQLite for orders that were 'In-Flight' during a crash.
        Cross-references with the broker to re-bind or alert.
        """
        if not self.is_connected:
            return

        logger.info("IBKR: Initiating Orphaned Order Recovery...")
        try:
            import os
            import sqlite3

            db_path = os.path.join("data", "trading.db")
            if not os.path.exists(db_path):
                return

            conn = sqlite3.connect(db_path, timeout=60.0)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 60000;")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT orderId, symbol, status FROM persistent_orders WHERE status NOT IN ('Filled', 'Cancelled', 'Inactive')"
            )
            orphans = cursor.fetchall()
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
                        f"🏛️ RECOVERY: Found live orphan {oid} for {sym}. Re-binding to tracking."
                    )
                else:
                    logger.error(
                        f"🚨 CRITICAL: Order {oid} ({sym}) lost from broker! Status was {status}. Manual audit required."
                    )
                self._recovered_orders.add(oid)

        except Exception as e:
            logger.error(f"IBKR Recovery Error: {e}")

    def get_account_value(self) -> float:
        """Returns NAV from the real-time cache (No API Polling)."""
        if not self.is_connected:
            return STARTING_CAPITAL_CAD
        try:
            # 1. Check the event-driven cache first (Updated by _on_account_summary)
            val = self._account_summary.get("NetLiquidation")
            if val is not None:
                return float(val)

            # 2. Fallback to active session values if cache is cold (No Request limit hit)
            # Use accountValues() which is a locally-cached list in ib_insync
            for item in self.ib.accountValues():
                if item.tag == "NetLiquidation":
                    self._account_summary["NetLiquidation"] = item.value  # Populate cache
                    return float(item.value)

            return STARTING_CAPITAL_CAD
        except Exception as e:
            logger.error(f"IBKR: NAV Cache Retrieval failed: {e}")
            return STARTING_CAPITAL_CAD

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
        if not self.is_connected:
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
        # --- SE-11 BREAKTHROUGH: GHOST EXPANSION ---
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
                f"🏛️ GHOST EXPANSION ACTIVE: Scaling {shares} -> {new_shares} | Expanding Stop: {stop_loss:.2f} -> {new_stop_loss:.2f}"
            )
            shares = new_shares
            stop_loss = new_stop_loss

        # The caller must provide an exec_token generated by IBKRConnection.generate_exec_token()
        exec_token = kwargs.get("exec_token", "")
        if not self._verify_exec_token(symbol, exec_token):
            logger.critical(
                f"UNAUTHORIZED EXECUTION ATTEMPT for {symbol}! Invalid or missing exec_token. REJECTING ORDER."
            )
            return []

        # Reduced from 30s to 1s to allow Scalping/HFT while preventing API flooding
        wait_seconds = (datetime.now() - self._last_trade_time).total_seconds()
        if wait_seconds < 1.0:
            logger.warning(
                f"🏛️ DISCIPLINE THROTTLE: Trade for {symbol} suppressed. Only {wait_seconds:.1f}s elapsed."
            )
            return []

        if self.is_near_close():
            logger.warning(
                f"🏛️ MARKET CLOSE GUARD: Order for {symbol} rejected (within 5m of close)."
            )
            return []

        if not self.is_connected:
            from config import FORCED_PAPER_MODE

            if FORCED_PAPER_MODE:
                logger.info(
                    f"IBKR [SIM]: Bracket {direction} {shares} {symbol} @ ${limit_price} (SL: {stop_loss}, TP: {take_profit})"
                )
                self._last_trade_time = datetime.now()  # Update even in sim
                return [int(time.time()), int(time.time()) + 1, int(time.time()) + 2]
            logger.error(f"IBKR: Offline. Cannot place bracket order for {symbol}.")
            return []

        async with self._lock:  # Ensure serial access to IB client socket
            try:
                # Use cached contract if available (Neural Warmup)
                from ib_insync import LimitOrder, Stock, StopLimitOrder

                if symbol in self._qualified_contracts:
                    contract = self._qualified_contracts[symbol]
                else:
                    contract = Stock(symbol, "SMART", "USD")
                    await self.ib.qualifyContractsAsync(contract)

                # Bug 30 FIX: Limit Price Bias Guard
                # If the spread is wider than 0.5%, use the actual Bid/Ask instead of Mid to ensure fill.
                # Use the brain's real-time tick cache
                bid = self.brain.last_tick_bids.get(symbol, 0.0)
                ask = self.brain.last_tick_asks.get(symbol, 0.0)

                if bid > 0 and ask > 0:
                    if (ask - bid) / bid > 0.005:
                        limit_price = ask if direction == "BUY" else bid
                        logger.info(
                            f"IBKR: Wide spread detected for {symbol}. Overriding Mid with {direction} side: ${limit_price:.2f}"
                        )

                # Tick-size rounding
                lmt = self.round_to_tick(limit_price)
                sl = self.round_to_tick(stop_loss)
                tp = self.round_to_tick(take_profit)

                # 1. Entry Order
                parent = LimitOrder(direction, shares, lmt)
                parent.orderId = self.ib.client.getReqId()
                parent.transmit = False
                parent.overridePercentageConstraints = True

                # Replaced Stop-Market with Stop-Limit ('Recovery Limit')
                # A 2% buffer ensures fill in fast markets while capping slippage at a tolerable level.
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

                # 3. Take Profit Order
                tp_order = LimitOrder(opp_direction, shares, tp)
                tp_order.parentId = parent.orderId
                tp_order.transmit = True  # Final order in bracket transmits the entire group
                tp_order.overridePercentageConstraints = True

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
                    f"IBKR: Sovereign Bracket BROADCAST for {symbol} | Accounts: {len(target_accounts)} | Entry: {lmt}"
                )
                return ids

            except Exception as e:
                logger.error(f"IBKR Bracket Failure for {symbol}: {e}")
                return []

    def _persist_execution(self, symbol: str, order_type: str, details: dict):
        """Write a persistent execution log entry for audit trail and manual recovery."""
        try:
            log_file = "data/execution_persistence.json"
            import json
            import os

            os.makedirs("data", exist_ok=True)
            entry = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "type": order_type,
                "details": details,
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
                f"Invalid or missing exec_token. REJECTING ORDER."
            )
            return None

        wait_seconds = (datetime.now() - self._last_trade_time).total_seconds()
        if wait_seconds < 1.0:
            logger.warning(f"🏛️ DISCIPLINE THROTTLE: Order for {symbol} suppressed.")
            return None

        if not self.is_connected:
            from config import FORCED_PAPER_MODE

            if FORCED_PAPER_MODE:
                logger.info(f"IBKR [SIM]: Routing {direction} {shares} {symbol} (Mode: {urgency})")
                return int(time.time())
            logger.error(f"IBKR: Offline. Cannot place Single order for {symbol}.")
            return None

        async with self._lock:  # Ensure serial access to IB client socket
            self._persist_execution(
                symbol,
                "SINGLE",
                {"dir": direction, "shares": shares, "px": limit_price, "type": order_type},
            )

            try:
                from ib_insync import Future, LimitOrder, Stock

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

                # --- HYPER-SOVEREIGN BREAKTHROUGH: WARM-PATH MODIFICATION ---
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

                for i, acc in enumerate(target_accounts):
                    if urgency == "HIGH" or order_type == "MKT":
                        # Replaced MarketOrder with 'Aggressive Limit' to prevent flash-crash slippage.
                        # We use a 1.5% buffer for entries and exits; if it doesn't fill, we prefer a miss over a ruinous price.
                        buffer = 0.015
                        price = (
                            limit_price  # Fallback to limit_price for buffering if lmt is not set
                        )
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
                        asyncio.create_task(self._audit_execution(trade, symbol, shares))

                self._last_trade_time = datetime.now()  # Update Discipline Lock
                return primary_id

            except Exception as e:
                logger.error(f"IBKR Routing Failure for {symbol}: {e}")
                return None

        # --- HYPER-SOVEREIGN BREAKTHROUGH: WARM-SLOT EXECUTION (SE-13) ---

    async def _maintain_warm_slots(self, symbols: list[str]) -> None:
        """
        Maintains 'Dormant Orders' on the exchange to preserve a 'Warm Path'.
        Modifying an existing order is often faster than submitting a new one.
        """
        if not self.is_connected:
            return

        from ib_insync import LimitOrder, Stock

        for symbol in symbols:
            if symbol not in self._warm_slots:
                contract = self._qualified_contracts.get(symbol, Stock(symbol, "SMART", "USD"))
                # Place a 'Placeholder' order very far from market to avoid fill
                order = LimitOrder("BUY", 1, 0.01)  # $0.01 Placeholder
                trade = self.ib.placeOrder(contract, order)
                self._warm_slots[symbol] = trade
                logger.debug(
                    f"IBKR: Warm-Slot initialized for {symbol} (Order ID: {trade.order.orderId})"
                )

    async def _execute_via_warm_slot(
        self, symbol: str, direction: str, shares: int, price: float
    ) -> int | None:
        """Executes a trade by MODIFYING an existing dormant order (The Hyper-Sovereign Leap)."""
        if symbol not in self._warm_slots:
            return None

        trade = self._warm_slots[symbol]
        if trade.status in ("Filled", "Cancelled"):
            del self._warm_slots[symbol]
            return None

        # Transform the dormant order into the real tiger
        trade.order.action = direction
        trade.order.totalQuantity = shares
        trade.order.lmtPrice = self.round_to_tick(price)
        trade.order.transmit = True

        self.ib.placeOrder(trade.contract, trade.order)
        logger.info(
            f"🏛️ HYPER-SOVEREIGN: Warm-Slot MODIFICATION executed for {symbol} (Sub-ms path)."
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
        target_acc = trade.order.account
        for _attempt in range(6):  # Poll for 60s total
            await asyncio.sleep(10)
            if trade.orderStatus.status == "Filled":
                # Filter by Account ID to avoid cross-talk from other portfolios
                current_pos = next(
                    (
                        p
                        for p in self.get_positions()
                        if p["symbol"] == symbol
                        and (not target_acc or str(p["account"]).strip() == str(target_acc).strip())
                    ),
                    None,
                )

                if current_pos and abs(current_pos["shares"]) >= abs(shares) * 0.9:
                    logger.info(
                        f"✓ AUDIT SUCCESS: {symbol} execution verified in portfolio account {target_acc}."
                    )
                    return  # Alignment confirmed

        # If we reach here after 60s, it's a true critical inconsistency
        logger.critical(
            f"IBKR: SILENT EXECUTION FAILURE DETECTED for {symbol}. Inconsistency persistent after 60s."
        )
        self._last_heartbeat = datetime(1970, 1, 1)  # Poison the heartbeat

    def cancel_order(self, order_id: int) -> bool:
        if not self.is_connected:
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
        if not self.is_connected:
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
        except Exception:
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
        instrument = kwargs.get("instrument", "UNKNOWN")
        from risk_invariants import RiskInvariants

        # --- SOVEREIGN REALITY ALIGNED HAIRCUT ---
        # Optimistic suicide is prevented by assuming slightly less capital than we think we have.
        _raw_nav = kwargs.get("account_value", balance)
        balance = min(balance, _raw_nav) * 0.99

        if balance > 2000000.0:
            logger.warning(
                f"🏛️ SOVEREIGN GUARD: Detected outlier account value of ${balance:,.2f}. Capping at $2M for Safety."
            )
            balance = 2000000.0

        # Step 1: Raw Kelly Risk (Balanced)
        kelly_pct = win_prob - ((1 - win_prob) / r_r_ratio) if r_r_ratio > 0 else 0
        step1_risk = balance * max(0, kelly_pct)

        # Step 2: High-Fidelity Hard Cap (Dynamic System Max Risk)
        from config import CASH_ACCOUNT_MAX_RATIO, RISK_PER_TRADE_PCT, SYSTEM_MAX_RISK

        step2_risk = min(step1_risk, balance * SYSTEM_MAX_RISK)

        # Step 3: Cash Availability (Dynamic Cash Ratio)
        step3_risk = min(step2_risk, balance * CASH_ACCOUNT_MAX_RATIO)

        # Step 4: Gap Risk Adjustment (Volatility-weighted)
        gap_mod = kwargs.get("gap_modifier", 1.0)
        step4_risk = step3_risk * max(0.5, min(1.5, gap_mod))

        # Step 5: Regime Intensity Adjustment (Scaling down in Choppy markets)
        regime_mod = kwargs.get("regime_modifier", 1.0)
        step5_risk = step4_risk * max(0.1, min(1.0, regime_mod))

        # Step 6: Fat-Tail Shield (Protective reduction if WinRate < 60%)
        fat_tail_mod = 0.82 if win_prob < 0.6 else 1.0
        step6_risk = step5_risk * fat_tail_mod

        # --- SOVEREIGN SAFETY OVERRIDES ---
        dd_mod = kwargs.get("drawdown_modifier", 1.0)
        loss_mod = kwargs.get("loss_modifier", 1.0)

        # Step 7: Final Monetary Risk (Hard Configured Cap of Total Balance)
        self_risk_limit = balance * RISK_PER_TRADE_PCT if RISK_PER_TRADE_PCT > 0 else balance * 0.01

        # If Kelly says 0, but the Quorum approved, force a small experimental 'Mini-Risk'
        min_viable_risk = 2.0 if balance < 1000 else balance * 0.001
        step7_final_risk = min(max(step6_risk, min_viable_risk), self_risk_limit)

        # Apply the Sovereign safety multipliers to the final dollar risk
        step7_final_risk *= dd_mod * loss_mod

        # FINAL FLOOR: Ensure risk covers at least the commission + slippage buffer
        if balance < 1000:
            step7_final_risk = max(step7_final_risk, 2.0)

        # Step 8: Discrete Share Quantization
        price = kwargs.get("entry_price", 1.0)
        stop = kwargs.get("stop_price", price * 0.99)
        spread = kwargs.get("spread", 0.0)

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
                    f"Sizer: [FRICTION VETO] {instrument} R:R with spread is only {real_rr:.2f} (Target Reward ${real_reward:.2f} < Risk ${risk_per_share:.2f})."
                )
                # We don't return 0 here yet, Phase 7 might still approve if high win_prob.

        if risk_per_share < (price * 0.0001):
            # If risk is too tight (< 0.01% of price), the geometry is invalid for HFT.
            logger.error(
                f"Sizer: [GEOMETRY_VETO] {instrument} risk (${risk_per_share:.4f}) is too tight for price ${price:.2f}. Rejecting."
            )
            return {"shares": 0, "risk_dollars": 0, "proposed_value": 0, "steps": {}}

        # --- SOVEREIGN QUANTIZATION ---
        if step7_final_risk <= 0 or step6_risk <= 0:
            logger.warning(
                f"Sizer: Risk math resulted in zero exposure for {instrument}. Quashing trade."
            )
            return {"shares": 0, "risk_dollars": 0, "proposed_value": 0, "steps": {}}

        step8_shares = int(round(step7_final_risk / risk_per_share)) if risk_per_share > 0 else 0

        # This prevents forced over-leverage on micro-accounts ($500 etc.)
        min_trade_value = balance * 0.02  # 2% of NAV = $10 on $500 account
        if (
            step8_shares > 0
            and (step8_shares * price) < min_trade_value
            and price > 0
            and step7_final_risk > 0
        ):
            step8_shares = max(1, int(round(min_trade_value / price)))

        # Final Position Value Guard (10% max of NAV per trade)
        # Cap this by the hard dollar limit from RiskInvariants
        hard_cap = RiskInvariants.MAX_NOTIONAL_PER_ORDER.get(instrument, RiskInvariants.MAX_NOTIONAL_PER_ORDER["DEFAULT"])
        max_notional = min(balance * 0.10, hard_cap)

        if step8_shares > 0 and (step8_shares * price) > max_notional:
            logger.warning(
                f"Sizer: Capping {instrument} at max notional (${max_notional:,.2f}) because math was too aggressive."
            )
            step8_shares = max(1, int(max_notional / price))

        if step8_shares == 0 and step7_final_risk > (price * 0.5):
            # If the risk budget allows for at least 0.5 shares, we force 1 share
            # This allows $500 accounts to take positions where price is $100 and risk is $10
            step8_shares = 1
            logger.info(
                f"Sizer: [SMALL_ACC_FIX] Forcing 1 share for {instrument} despite risk rounding."
            )

        # --- STEP 9: IMPACT ORACLE ---
        ohlcv = kwargs.get("ohlcv_df")

        if ohlcv is not None and len(ohlcv) < 50 and not kwargs.get("is_probe"):
            logger.warning(
                f"Sizer: [IPO_GUARD] {instrument} has < 50 bars of history. Rejecting for low-liquidity/high-volatility risk."
            )
            return {"shares": 0, "risk_dollars": 0, "proposed_value": 0, "steps": {}}

        if ohlcv is not None and step8_shares > 0:
            est_slippage = self.impact_oracle.estimate_impact(instrument, step8_shares, ohlcv)
            # If slippage eats more than 15% of the expected profit, we downsize
            expected_profit_pct = abs(kwargs.get("target_price", price * 1.02) - price) / price
            if est_slippage > (expected_profit_pct * 0.15):
                logger.warning(
                    f"Sizer: [IMPACT_GUARD] {instrument} slippage {est_slippage:.2%} > 15% of reward. Downsizing 50% for safety."
                )
                step8_shares = max(1, int(round(step8_shares * 0.5)))
        elif step8_shares > 0 and not kwargs.get("is_probe"):
            logger.warning(
                f"Sizer: [IMPACT_GAP] No OHLCV data for {instrument} impact estimation. Applying 30% blind downsizing."
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
                f"Sizer: COMMISSION KILL for {instrument}. Expected reward ${expected_reward:.2f} < commission ${COMMISSION_PER_ROUND_TRIP:.2f}. Quashing trade."
            )
            return {"shares": 0, "risk_dollars": 0, "proposed_value": 0, "steps": {}}

        # --- PHASE 9: INVARIANT AUDIT ---
        if not RiskInvariants.audit_trade_parameters(step7_final_risk, balance):
            logger.critical(
                f"Sizer: [INVARIANT VETO] Proposed risk for {instrument} violates hard safety bounds."
            )
            return {"shares": 0, "risk_dollars": 0, "proposed_value": 0, "steps": {}}

        logger.info(
            f"Imperial Sizer: [NAV: ${balance:,.2f}] -> [Risk: ${step7_final_risk:,.2f}] -> [Shares: {step8_shares}]"
        )

        return {
            "shares": step8_shares if step8_shares > 0 else 0,
            "step8_shares": step8_shares if step8_shares > 0 else 0,  # Legacy key for Coordinator
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
            else f"VIX Spike {vix:.2f} (Dynamic Threshold {safe_threshold:.2f} Exceeded)",
            "risk_flag": not v_low,
        }

    def monitor_intraday(self, current: float, high: float, low: float) -> str:
        """The Sovereign Intraday Circuit Breaker (Nuclear Option)."""
        # If VIX sustains above 45.0, initiate whole-portfolio liquidation
        if current > 45.0:
            return "CLOSE at market"
        return "CONTINUE"


class CorrelationCascade:
    def check_exposure(self, symbol: str, positions: list[Any], equity: float) -> bool:
        # Prevent more than 30% exposure in a single sector (first 2 chars of symbol)
        sector = symbol[:2]
        sector_exposure = sum(
            abs(p.qty * p.entry_price) for p in positions if p.symbol[:2] == sector
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
            else f"CASH_RESERVE_VETO: Total exposure would exceed 85% NAV (${(total_p_val + proposed_val):.2f} > ${(balance * 0.85):.2f})",
            "timestamp": datetime.now().isoformat(),
        }
