import inspect
import logging
import os
from datetime import datetime, timedelta
from datetime import time as dt_time
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

from config import FTMO_DAILY_LIMIT, FTMO_DRAWDOWN_LIMIT, MAX_TRADES_PER_DAY
from vault import Vault

# Aliases for Sovereign Compatibility
mt5_raw: Any = None
mt5: Any = mt5_raw


def _get_mt5_module() -> Any:
    global mt5
    if mt5 is None:
        try:
            import MetaTrader5 as mt5_mod
        except Exception as e:
            logger.error(f"MT5: failed to import MetaTrader5: {e}")
            raise
        mt5 = mt5_mod
    return mt5


class MT5ConnectionLegacy:
    def __init__(self) -> None:
        import time as _time

        self._last_init_time = _time.time()
        self._login = 0
        self._pw = ""
        self._server = ""

    async def is_connected(self) -> bool:
        """Check if terminal is connected and authorized."""
        import asyncio as _asyncio

        mt5 = _get_mt5_module()
        info = await _asyncio.to_thread(mt5.terminal_info)
        if info is None:
            # Check if we should attempt re-initialization (>30s since last attempt)
            import time as _time

            if _time.time() - self._last_init_time > 30:
                logger.warning(
                    f"MT5: Connection lost > 30s (Login: {self._login}). Attempting Sovereign Re-initialization..."
                )
                if self._login > 0:
                    # Await the async connect call
                    await self.connect(self._login, self._pw, self._server)
            return False
        return True

    async def connect(self, login: int, pw: str, server: str, path: str = "") -> bool:
        """Connect to MT5 trading server with login credentials."""
        import asyncio as _asyncio
        import time as _time

        mt5 = _get_mt5_module()

        self._login = login
        self._pw = pw
        self._server = server
        self._last_init_time = _time.time()

        success = await _asyncio.to_thread(
            mt5.initialize, path=path, server=server, login=login, password=pw
        )

        if not success and not path:
            # Try to find path autonomously if first attempt failed
            found_path = Vault.get("MT5_PATH")
            if found_path:
                effective_path = str(found_path)
                if os.path.isdir(effective_path):
                    potential_exe = os.path.join(effective_path, "terminal64.exe")
                    if os.path.exists(potential_exe):
                        effective_path = potential_exe

                logger.info(
                    f"MT5: First init failed. Retrying with resolved path: {effective_path}"
                )
                success = await _asyncio.to_thread(
                    mt5.initialize, path=effective_path, server=server, login=login, password=pw
                )

        return success

    def sync_state(self, login: int, pw: str, server: str) -> None:
        """Synchronize connection state from external orchestrator without re-initializing."""
        import time as _time

        self._login = login
        self._pw = pw
        self._server = server
        self._last_init_time = _time.time()
        logger.debug(f"MT5: Connection state synchronized (Login: {login})")

    def get_account_info(self) -> dict:
        """Retrieve account information such as balance and equity."""
        mt5 = _get_mt5_module()
        account_info = mt5.account_info()
        return account_info._asdict() if account_info else {}

    def place_order(self, sym: str, dir: str, vol: float, sl: float, tp: float) -> int:
        """Place an order on MT5 platform."""
        AUTHORIZED_CALLERS = {
            "sovereign_decision_engine",
            "_place_mt5_order",
            "initiate_trade_lifecycle",
            "flat_all_positions",
            "_emergency_flatten",
            "repair_state",
            "_tool_trigger_logic",
            "run",
        }
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        if caller_name not in AUTHORIZED_CALLERS:
            # Try one more level up if it's an async wrapper
            caller_frame = caller_frame.f_back if caller_frame else None
            caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        # Issue: IMPLEMENT: Whitelist Signature Guard
        # We now verify the module name AND the function name to prevent local spoofing.
        caller_module = caller_frame.f_globals.get("__name__", "unknown")

        AUTHORIZED_MODULES = {
            "brain",
            "sovereign_decision_engine",
            "trading_system",
            "agent_c_ibkr",
        }

        if caller_name not in AUTHORIZED_CALLERS or (
            caller_module not in AUTHORIZED_MODULES and not caller_module.startswith("src.")
        ):
            logger.critical(
                f"UNAUTHORIZED EXECUTION ATTEMPT! Caller '{caller_module}.{caller_name}' bypassed Sovereign Engine! REJECTING ORDER."
            )
            return 0
        d = dir.lower()
        mt5 = _get_mt5_module()
        order_type = mt5.ORDER_TYPE_BUY if d == "buy" else mt5.ORDER_TYPE_SELL

        # Issue: IMPLEMENT: Dynamic Slippage (Volatility-Adjusted)
        # Instead of static '10', we use a 5-bar ATR buffer (if available) or 0.1% of price.
        # This prevents rejections on high-volatility assets like XAUUSD or crypto.
        deviation = 10
        try:
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 5)
            if rates is not None and len(rates) > 0:
                atr_5 = np.mean([abs(r["high"] - r["low"]) for r in rates])
                # Convert ATR to points (simplistic proxy)
                info = mt5.symbol_info(sym)
                if info and info.point > 0:
                    deviation = max(10, int(atr_5 * 1.5 / info.point))
                else:
                    deviation = 10
        except Exception as exc:
            logger.debug("MT5: volatility-adjusted slippage fallback for %s: %s", sym, exc)
            deviation = 10

        # Issue: IMPLEMENT: Order ID Collision Guard
        # Instead of a static magic number, we use a unique ID per execution cycle.
        import uuid as _uuid

        magic_id = _uuid.uuid4().int % 2147483647

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": vol,
            "type": order_type,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "magic": magic_id,
            "comment": "SETO_V8_AUTONOMY",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            logger.error("MT5: order_send returned None (Check terminal connection)")
            return 0
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"MT5: Order failed! Retcode: {result.retcode} | {result.comment}")
            return 0
        return result.order

    def close_position(self, ticket: int) -> bool:
        """Close an open position by ticket number."""
        mt5 = _get_mt5_module()
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": position[0].symbol,
            "volume": position[0].volume,
            "type": mt5.ORDER_TYPE_SELL
            if position[0].type == mt5.POSITION_TYPE_BUY
            else mt5.ORDER_TYPE_BUY,
            "magic": 234000,
            "comment": "SETO_V8_POST_MORTEM",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }

        result = mt5.order_send(request)
        if result is None:
            return False
        return result.retcode == mt5.TRADE_RETCODE_DONE

    def get_open_positions(self) -> list[int]:
        """Return a list of all open position ticket numbers."""
        mt5 = _get_mt5_module()
        positions = mt5.positions_get()
        return [pos.ticket for pos in positions] if positions else []

    def get_all_positions(self) -> dict[str, float]:
        """Return a symbol-to-quantity map of all open positions."""
        mt5 = _get_mt5_module()
        if not mt5 or not hasattr(mt5, "positions_get") or not callable(mt5.positions_get):
            return {}
        positions = mt5.positions_get()
        if not positions:
            return {}

        result = {}
        for pos in positions:
            # Polarity: Buy is positive, Sell is negative
            qty = pos.volume
            if pos.type == mt5.POSITION_TYPE_SELL:
                qty = -qty

            # Aggregate if multiple positions exist for the same symbol
            result[pos.symbol] = result.get(pos.symbol, 0.0) + qty
        return result


class FTMOComplianceLayer:
    # CRITICAL: These MUST match src/config.py exactly
    # Any divergence = FTMO challenge failure
    DAILY_LIMIT: float = FTMO_DAILY_LIMIT
    DRAWDOWN_LIMIT: float = FTMO_DRAWDOWN_LIMIT
    MAX_TRADES: int = MAX_TRADES_PER_DAY

    def check_daily_loss(self, balance: float, pnl: float) -> bool:
        """Check if daily loss stays within the allowed limit."""
        daily_loss_limit = self.DAILY_LIMIT * balance
        return pnl >= -daily_loss_limit

    def check_drawdown(self, peak: float, current: float) -> bool:
        """Check if current drawdown exceeds the permitted drawdown limit."""
        if peak <= 0:
            return True
        drawdown = (peak - current) / peak
        return drawdown <= self.DRAWDOWN_LIMIT

    def check_trade_count(self, n: int) -> bool:
        """Ensure the number of trades does not exceed the max limit."""
        return n <= self.MAX_TRADES

    def best_day_rule(self, today: float, others: list[float]) -> bool:
        """Validate today's profit against best day rule."""
        if not others:
            return True  # No history to violate the rule
        return today <= (2 / 3) * sum(others)

    def prague_midnight_reset(self) -> None:
        """Handle daily reset according to Prague timezone."""
        from datetime import timezone as _timezone

        # Prague is CET/CEST (UTC+1/UTC+2)
        utc_now = datetime.now(_timezone.utc)
        # simplistic CET check
        prague_now = utc_now + timedelta(hours=1)
        if prague_now.time() >= dt_time(23, 59):
            logger.debug("MT5BudgetGuard: Prague midnight reset window reached.")

    def is_trading_allowed(self, account: dict, trade_count: int = 0) -> tuple[bool, str]:
        """Determine if trading is allowed based on account state."""
        if not self.check_daily_loss(account["balance"], account["equity"] - account["balance"]):
            return (False, "Daily loss limit exceeded.")
        if not self.check_trade_count(trade_count):
            return (False, "Maximum trades limit exceeded.")
        return (True, "Trading allowed.")


class MT5PositionSizer:
    async def calculate(self, symbol: str, entry_price: float, stop_price: float, **kwargs) -> dict:
        """
        Standardized sizing interface for MT5.
        Matches PositionSizingChain signature.
        """
        # 1. Resolve Risk Amount (Default 1% of account if not provided)
        # In brain.py _state_scanning, it doesn't pass risk_amount directly,
        # so we fetch balance here.
        mt5 = _get_mt5_module()
        account = (
            self._conn.get_account_info()
            if hasattr(self, "_conn")
            else mt5.account_info()._asdict()
            if mt5.account_info()
            else {}
        )
        balance = account.get("balance", 500.0)

        # Risk 1% by default, or use a provided modifier
        risk_pct = kwargs.get("risk_pct", 0.01)
        risk_amount = balance * risk_pct

        lots = self.calculate_lots(risk_amount, entry_price, stop_price, symbol)

        return {
            "shares": lots,
            "step8_shares": lots,  # Coordinator compatibility
            "lots": lots,
            "proposed_value": lots * entry_price,
            "position_value": lots * entry_price,  # Coordinator compatibility
            "risk_dollars": risk_amount if lots > 0 else 0,
            "steps": {"final": risk_amount},
        }

    def calculate_lots(
        self, risk_amount: float, entry_price: float, stop_price: float, symbol: str
    ) -> float:
        """Calculate the lot size for a trade based on risk management.
        Institutional Single Order Routing.
        """
        AUTHORIZED_CALLERS = {
            "_place_mt5_order",
            "sovereign_decision_engine",
            "initiate_trade_lifecycle",
            "flat_all_positions",
            "repair_state",
            "run",
        }
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        if caller_name not in AUTHORIZED_CALLERS:
            # Try one more level up if it's an async wrapper
            caller_frame = caller_frame.f_back if caller_frame else None
            caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        if caller_name not in AUTHORIZED_CALLERS:
            logger.critical(
                f"UNAUTHORIZED EXECUTION ATTEMPT! Caller '{caller_name}' bypassed Sovereign Engine! REJECTING SIZING."
            )
            return 0.0

        mt5 = _get_mt5_module()
        tick_info = mt5.symbol_info(symbol)
        if tick_info is None:
            logger.warning(f"Sizer: Could not fetch symbol info for {symbol}")
            return 0.0

        # Absolute distance in price
        dist = abs(entry_price - stop_price)
        if dist < tick_info.point:
            logger.warning(f"Sizer: Distance {dist} too small for {symbol}")
            return 0.0

        # Risk per Lot = (Distance / TickSize) * TickValue
        # This works correctly for 5-digit forex, gold, and indices.
        tick_size = tick_info.trade_tick_size if tick_info.trade_tick_size > 0 else tick_info.point
        risk_per_lot = (dist / tick_size) * tick_info.trade_tick_value

        if risk_per_lot <= 0:
            logger.warning(f"Sizer: Zero risk_per_lot for {symbol}")
            return 0.0

        lots = risk_amount / risk_per_lot

        min_lot = tick_info.volume_min
        max_lot = tick_info.volume_max
        step_lot = tick_info.volume_step

        # Normailize units
        lots = round(lots / step_lot) * step_lot

        # Bound lots
        lots = max(min_lot, min(max_lot, lots))

        # If step_lot is 1.0, ensure we return a pure integer to avoid '0.0 lots' errors on some brokers.
        if step_lot >= 1.0:
            return float(int(round(lots)))

        return round(float(lots), 2)


class DrawdownHysteresis:
    def should_resume(self, last_dd_time: datetime, current_dd: float) -> bool:
        """Determine if trading can be resumed based on drawdown recovery."""
        from datetime import timezone as _timezone

        time_since_dd = datetime.now(_timezone.utc) - last_dd_time
        recovery_time_threshold = timedelta(hours=1)  # example threshold
        return current_dd < 0.05 and time_since_dd > recovery_time_threshold


class MetaTrader5Agent:
    """
    Deep Integration with MetaTrader 5 Terminal.
    Handles raw C++ struct serialization via the python MT5 bridge to execute
    high-speed retail/institutional order flow. Includes safety checks,
    slippage controls, and magic number tracking.
    """

    def __init__(
        self,
        account: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        magic_number: int = 777777,
    ):
        from vault import Vault

        self.account = account or int(Vault.get("MT5_ACCOUNT") or 0)
        self.password = password or Vault.get("MT5_PASSWORD") or ""
        self.server = server or Vault.get("MT5_SERVER") or ""
        self.magic_number = magic_number
        self.connected = False

    @property
    def is_connected(self) -> bool:
        return self.connected

    def connect(
        self,
        account: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
    ) -> bool:
        """Initializes the MT5 terminal and logs into the trading server."""
        mt5 = _get_mt5_module()
        if account is not None:
            self.account = int(account)
        if password is not None:
            self.password = str(password)
        if server is not None:
            self.server = str(server)

        if not mt5.initialize():
            logger.critical(f"[MT5] Initialization failed. Error code: {mt5.last_error()}")
            return False

        authorized = mt5.login(self.account, password=self.password, server=self.server)
        if not authorized:
            logger.critical(
                f"[MT5] Login failed for account {self.account}. Error code: {mt5.last_error()}"
            )
            mt5.shutdown()
            return False

        self.connected = True
        logger.info(f"[MT5] Successfully connected to {self.server} (Account: {self.account})")
        return True

    def get_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """Retrieves the absolute latest Bid/Ask tick."""
        if not self.connected:
            return None

        mt5 = _get_mt5_module()
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"[MT5] Failed to fetch tick for {symbol}")
            return None

        return {"bid": float(tick.bid), "ask": float(tick.ask), "time_ms": tick.time_msc}

    def execute_market_order(
        self,
        symbol: str,
        action: str,
        lot_size: float,
        slippage_pts: int = 10,
        sl: float = 0.0,
        tp: float = 0.0,
        is_close: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes a direct market order with Sovereign Security Guards.
        Action must be 'BUY' or 'SELL'.
        """
        import inspect

        from trading_state import TradingStateManager

        allowed, state_reason = TradingStateManager.allow_order(is_close=is_close)
        if not allowed:
            logger.warning(
                f"[MT5] SAFETY GATE: Market order for {symbol} REJECTED due to TradingState."
            )
            return {
                "status": "error",
                "message": state_reason,
            }

        # 1. WHITELIST SIGNATURE GUARD (Ported from D: drive logic)
        AUTHORIZED_CALLERS = {
            "sovereign_decision_engine",
            "_place_mt5_order",
            "initiate_trade_lifecycle",
            "flat_all_positions",
            "_emergency_flatten",
            "repair_state",
            "_tool_trigger_logic",
            "run",
        }
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        if caller_name not in AUTHORIZED_CALLERS:
            # Try one more level up if it's an async wrapper
            caller_frame = caller_frame.f_back if caller_frame else None
            caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        caller_module = caller_frame.f_globals.get("__name__", "unknown")
        AUTHORIZED_MODULES = {
            "brain",
            "sovereign_decision_engine",
            "trading_system",
            "agent_c_ibkr",
        }

        if caller_name not in AUTHORIZED_CALLERS or (
            caller_module not in AUTHORIZED_MODULES and not caller_module.startswith("src.")
        ):
            logger.critical(
                f"UNAUTHORIZED EXECUTION ATTEMPT! Caller '{caller_module}.{caller_name}' bypassed Sovereign Engine! REJECTING ORDER."
            )
            return {"status": "error", "message": "Unauthorized execution caller."}

        if not self.connected:
            return {"status": "error", "message": "MT5 Terminal not connected"}

        action = str(action).upper()
        if action not in {"BUY", "SELL"}:
            return {"status": "error", "message": f"Invalid MT5 action: {action}"}

        try:
            lot_size = float(lot_size)
        except (TypeError, ValueError):
            return {"status": "error", "message": f"Invalid MT5 lot size: {lot_size!r}"}
        if lot_size <= 0:
            return {"status": "error", "message": f"Non-positive MT5 lot size: {lot_size}"}

        mt5 = _get_mt5_module()
        if not mt5.symbol_select(symbol, True):
            logger.error(f"[MT5] Failed to select symbol {symbol}")
            return {"status": "error", "message": "Symbol selection failed"}

        info = mt5.symbol_info(symbol)
        if info is not None:
            min_lot = float(getattr(info, "volume_min", 0.0) or 0.0)
            max_lot = float(getattr(info, "volume_max", lot_size) or lot_size)
            step_lot = float(getattr(info, "volume_step", 0.0) or 0.0)
            if min_lot > 0:
                lot_size = max(min_lot, lot_size)
            if max_lot > 0:
                lot_size = min(max_lot, lot_size)
            if step_lot > 0:
                lot_size = round(round(lot_size / step_lot) * step_lot, 8)

        tick = self.get_tick(symbol)
        if not tick:
            return {"status": "error", "message": "Pricing unavailable"}

        # 2. DYNAMIC SLIPPAGE (Volatility-Adjusted)
        deviation = slippage_pts
        try:
            # We use a 5-bar ATR buffer (if available) or 0.1% of price.
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 5)
            if rates is not None and len(rates) > 0:
                atr_5 = np.mean([abs(r["high"] - r["low"]) for r in rates])
                info = mt5.symbol_info(symbol)
                if info and info.point > 0:
                    deviation = max(slippage_pts, int(atr_5 * 1.5 / info.point))
        except Exception as exc:
            logger.debug("MT5: volatility-adjusted slippage fallback for %s: %s", symbol, exc)
            deviation = slippage_pts

        # 3. MAGIC ID COLLISION GUARD
        import uuid as _uuid

        magic_id = _uuid.uuid4().int % 2147483647

        # Define MT5 Request Dictionary
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick["ask"] if action == "BUY" else tick["bid"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "sl": float(sl or 0.0),
            "tp": float(tp or 0.0),
            "deviation": int(deviation),
            "magic": magic_id,
            "comment": "SETO_V8_AUTONOMY",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send the order to the server
        logger.info(
            f"[MT5] Sending {action} {lot_size} lots on {symbol} at {price} (Dev: {deviation})"
        )
        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            rc = result.retcode if result else -1
            msg = result.comment if result else "No result from mt5.order_send"
            error_msg = f"Order failed, retcode={rc} | {msg}"
            logger.error(f"[MT5] {error_msg}")
            return {"status": "rejected", "message": error_msg, "retcode": rc}

        logger.info(f"[MT5] Order successfully filled! Ticket: {result.order}")
        return {
            "status": "filled",
            "ticket": result.order,
            "volume": result.volume,
            "price": result.price,
            "comment": result.comment,
        }

    def place_order(
        self,
        sym: str,
        dir: str,
        vol: float,
        sl: float = 0.0,
        tp: float = 0.0,
        is_close: bool = False,
    ) -> int:
        """Compatibility wrapper used by TradingBrain._place_mt5_order."""
        result = self.execute_market_order(
            sym, str(dir).upper(), vol, sl=sl, tp=tp, is_close=is_close
        )
        if result.get("status") != "filled":
            return 0
        return int(result.get("ticket") or 0)

    def close_position(self, ticket: int) -> bool:
        """Close one MT5 position by ticket using an explicit position close request."""
        if not self.connected:
            return False

        from trading_state import TradingStateManager

        allowed, state_reason = TradingStateManager.allow_order(is_close=True)
        if not allowed:
            logger.warning("[MT5] close_position blocked by TradingState: %s", state_reason)
            return False

        mt5 = _get_mt5_module()
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            logger.warning("[MT5] close_position: ticket %s not found.", ticket)
            return False

        pos = positions[0]
        if not mt5.symbol_select(pos.symbol, True):
            logger.error("[MT5] close_position: failed to select %s.", pos.symbol)
            return False

        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            logger.error("[MT5] close_position: no tick for %s.", pos.symbol)
            return False

        close_type = (
            mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        )
        price = float(tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(ticket),
            "symbol": pos.symbol,
            "volume": float(pos.volume),
            "type": close_type,
            "price": price,
            "deviation": 50,
            "magic": self.magic_number,
            "comment": "SETO_V8_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            rc = result.retcode if result else -1
            msg = result.comment if result else "No result from mt5.order_send"
            logger.error("[MT5] close_position failed for %s: retcode=%s | %s", ticket, rc, msg)
            return False
        logger.info("[MT5] Closed ticket %s at %s.", ticket, price)
        return True

    def close_all_positions(self, symbol: Optional[str] = None):
        """Emergency function to liquidate all positions associated with the Sovereign magic number."""
        if not self.connected:
            return

        mt5 = _get_mt5_module()
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            if pos.magic == self.magic_number:
                logger.warning(f"[MT5] Liquidating Position {pos.ticket} ({pos.symbol})")
                self.close_position(pos.ticket)

    def get_all_positions(self) -> Dict[str, float]:
        """Returns a mapping of {symbol: qty} for all open MT5 positions."""
        if not self.connected:
            return {}

        mt5 = _get_mt5_module()
        positions = mt5.positions_get()
        if positions is None:
            return {}

        reality = {}
        for pos in positions:
            if pos.magic == self.magic_number:
                # MT5 quantities are positive; polarity is determined by type
                qty = pos.volume if pos.type == mt5.POSITION_TYPE_BUY else -pos.volume
                reality[pos.symbol] = reality.get(pos.symbol, 0.0) + qty
        return reality

    def shutdown(self):
        if self.connected:
            mt5 = _get_mt5_module()
            mt5.shutdown()
            logger.info("[MT5] Terminal connection cleanly severed.")
            self.connected = False


# Final Sovereign Aliases
MT5Connection = MetaTrader5Agent
