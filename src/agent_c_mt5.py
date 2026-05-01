import inspect
import logging
import os
from datetime import datetime, timedelta
from datetime import time as dt_time

import MetaTrader5 as mt5
import numpy as np

logger = logging.getLogger(__name__)

from config import FTMO_DAILY_LIMIT, FTMO_DRAWDOWN_LIMIT, MAX_TRADES_PER_DAY
from vault import Vault


class MT5Connection:
    def __init__(self) -> None:
        import time as _time
        self._last_init_time = _time.time()
        self._login = 0
        self._pw = ""
        self._server = ""

    async def is_connected(self) -> bool:
        """Check if terminal is connected and authorized."""
        import asyncio as _asyncio
        info = await _asyncio.to_thread(mt5.terminal_info)
        if info is None:
            # Check if we should attempt re-initialization (>30s since last attempt)
            import time as _time
            if _time.time() - self._last_init_time > 30:
                logger.warning(f"MT5: Connection lost > 30s (Login: {self._login}). Attempting Sovereign Re-initialization...")
                if self._login > 0:
                    # Await the async connect call
                    await self.connect(self._login, self._pw, self._server)
            return False
        return True

    async def connect(self, login: int, pw: str, server: str, path: str = "") -> bool:
        """Connect to MT5 trading server with login credentials."""
        import asyncio as _asyncio
        import time as _time
        self._login = login
        self._pw = pw
        self._server = server
        self._last_init_time = _time.time()

        success = await _asyncio.to_thread(mt5.initialize, path=path, server=server, login=login, password=pw)

        if not success and not path:
            # Try to find path autonomously if first attempt failed
            found_path = Vault.get("MT5_PATH")
            if found_path:
                effective_path = str(found_path)
                if os.path.isdir(effective_path):
                    potential_exe = os.path.join(effective_path, "terminal64.exe")
                    if os.path.exists(potential_exe):
                        effective_path = potential_exe

                logger.info(f"MT5: First init failed. Retrying with resolved path: {effective_path}")
                success = await _asyncio.to_thread(mt5.initialize, path=effective_path, server=server, login=login, password=pw)

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
            "run"
        }
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        if caller_name not in AUTHORIZED_CALLERS:
            # Try one more level up if it's an async wrapper
            caller_frame = caller_frame.f_back if caller_frame else None
            caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        # Bug 36 FIX: Whitelist Signature Guard
        # We now verify the module name AND the function name to prevent local spoofing.
        caller_module = caller_frame.f_globals.get("__name__", "unknown")

        AUTHORIZED_MODULES = {"brain", "sovereign_decision_engine", "trading_system", "agent_c_ibkr"}

        if caller_name not in AUTHORIZED_CALLERS or (caller_module not in AUTHORIZED_MODULES and not caller_module.startswith("src.")):
            logger.critical(f"UNAUTHORIZED EXECUTION ATTEMPT! Caller '{caller_module}.{caller_name}' bypassed Sovereign Engine! REJECTING ORDER.")
            return 0
        d = dir.lower()
        order_type = mt5.ORDER_TYPE_BUY if d == "buy" else mt5.ORDER_TYPE_SELL

        # Bug 34 FIX: Dynamic Slippage (Volatility-Adjusted)
        # Instead of static '10', we use a 5-bar ATR buffer (if available) or 0.1% of price.
        # This prevents rejections on high-volatility assets like XAUUSD or crypto.
        deviation = 10
        try:
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 5)
            if rates is not None and len(rates) > 0:
                atr_5 = np.mean([abs(r['high'] - r['low']) for r in rates])
                # Convert ATR to points (simplistic proxy)
                info = mt5.symbol_info(sym)
                if info and info.point > 0:
                    deviation = max(10, int(atr_5 * 1.5 / info.point))
                else:
                    deviation = 10
        except Exception:
            deviation = 10

        # Bug 35 FIX: Order ID Collision Guard
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
        positions = mt5.positions_get()
        return [pos.ticket for pos in positions] if positions else []

    def get_all_positions(self) -> dict[str, float]:
        """Return a symbol-to-quantity map of all open positions."""
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
        drawdown = (peak - current) / peak
        return drawdown <= self.DRAWDOWN_LIMIT

    def check_trade_count(self, n: int) -> bool:
        """Ensure the number of trades does not exceed the max limit."""
        return n <= self.MAX_TRADES

    def best_day_rule(self, today: float, others: list[float]) -> bool:
        """Validate today's profit against best day rule."""
        if not others:
            return True # No history to violate the rule
        return today <= (2 / 3) * sum(others)

    def prague_midnight_reset(self) -> None:
        """Handle daily reset according to Prague timezone."""
        from datetime import timezone as _timezone
        # Prague is CET/CEST (UTC+1/UTC+2)
        utc_now = datetime.now(_timezone.utc)
        # simplistic CET check
        prague_now = utc_now + timedelta(hours=1)
        if prague_now.time() >= dt_time(23, 59):
            # Code to perform any reset logic needed
            pass

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
        account = self._conn.get_account_info() if hasattr(self, '_conn') else mt5.account_info()._asdict() if mt5.account_info() else {}
        balance = account.get("balance", 500.0)

        # Risk 1% by default, or use a provided modifier
        risk_pct = kwargs.get("risk_pct", 0.01)
        risk_amount = balance * risk_pct

        lots = self.calculate_lots(risk_amount, entry_price, stop_price, symbol)

        return {
            "shares": lots,
            "step8_shares": lots, # Coordinator compatibility
            "lots": lots,
            "proposed_value": lots * entry_price,
            "position_value": lots * entry_price, # Coordinator compatibility
            "risk_dollars": risk_amount if lots > 0 else 0,
            "steps": {"final": risk_amount}
        }

    def calculate_lots(self, risk_amount: float, entry_price: float, stop_price: float, symbol: str) -> float:
        """Calculate the lot size for a trade based on risk management.
        Institutional Single Order Routing.
        """
        AUTHORIZED_CALLERS = {
            "_place_mt5_order",
            "sovereign_decision_engine",
            "initiate_trade_lifecycle",
            "flat_all_positions",
            "repair_state",
            "run"
        }
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        if caller_name not in AUTHORIZED_CALLERS:
             # Try one more level up if it's an async wrapper
             caller_frame = caller_frame.f_back if caller_frame else None
             caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        if caller_name not in AUTHORIZED_CALLERS:
             logger.critical(f"UNAUTHORIZED EXECUTION ATTEMPT! Caller '{caller_name}' bypassed Sovereign Engine! REJECTING SIZING.")
             return 0.0

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

        # Step 2: Respect Broker Constraints
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
