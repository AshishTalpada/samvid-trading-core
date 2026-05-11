import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import MetaTrader5 as mt5_raw
import numpy as np

mt5: Any = mt5_raw

logger = logging.getLogger(__name__)

class MetaTrader5Agent:
    """
    Deep Integration with MetaTrader 5 Terminal.
    Handles raw C++ struct serialization via the python MT5 bridge to execute
    high-speed retail/institutional order flow. Includes safety checks,
    slippage controls, and magic number tracking.
    """
    def __init__(self, account: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None, magic_number: int = 777777):
        from vault import Vault
        self.account = account or int(Vault.get("MT5_ACCOUNT") or 0)
        self.password = password or Vault.get("MT5_PASSWORD") or ""
        self.server = server or Vault.get("MT5_SERVER") or ""
        self.magic_number = magic_number
        self.connected = False

    @property
    def is_connected(self) -> bool:
        return self.connected

    def connect(self) -> bool:
        """Initializes the MT5 terminal and logs into the trading server."""
        if not mt5.initialize():
            logger.critical(f"[MT5] Initialization failed. Error code: {mt5.last_error()}")
            return False

        authorized = mt5.login(self.account, password=self.password, server=self.server)
        if not authorized:
            logger.critical(f"[MT5] Login failed for account {self.account}. Error code: {mt5.last_error()}")
            mt5.shutdown()
            return False

        self.connected = True
        logger.info(f"[MT5] Successfully connected to {self.server} (Account: {self.account})")
        return True

    def get_tick(self, symbol: str) -> Optional[Dict[str, float]]:
        """Retrieves the absolute latest Bid/Ask tick."""
        if not self.connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"[MT5] Failed to fetch tick for {symbol}")
            return None

        return {
            "bid": float(tick.bid),
            "ask": float(tick.ask),
            "time_ms": tick.time_msc
        }

    def execute_market_order(self, symbol: str, action: str, lot_size: float, slippage_pts: int = 10) -> Dict[str, Any]:
        """
        Executes a direct market order with Sovereign Security Guards.
        Action must be 'BUY' or 'SELL'.
        """
        import inspect
        from trading_state import TradingStateManager
        if not TradingStateManager.allow_order(True): # MT5 orders are usually new entries in this context
            logger.warning(f"[MT5] SAFETY GATE: Market order for {symbol} REJECTED due to TradingState.")
            return {"status": "error", "message": f"TradingState {TradingStateManager.state.value} blocks entries"}

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
        AUTHORIZED_MODULES = {"brain", "sovereign_decision_engine", "trading_system", "agent_c_ibkr"}

        if caller_name not in AUTHORIZED_CALLERS or (
            caller_module not in AUTHORIZED_MODULES and not caller_module.startswith("src.")
        ):
            logger.critical(f"UNAUTHORIZED EXECUTION ATTEMPT! Caller '{caller_module}.{caller_name}' bypassed Sovereign Engine! REJECTING ORDER.")
            return {"status": "error", "message": "Unauthorized execution caller."}

        if not self.connected:
            return {"status": "error", "message": "MT5 Terminal not connected"}

        if not mt5.symbol_select(symbol, True):
            logger.error(f"[MT5] Failed to select symbol {symbol}")
            return {"status": "error", "message": "Symbol selection failed"}

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
        except Exception:
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
            "deviation": int(deviation),
            "magic": magic_id,
            "comment": "SETO_V8_AUTONOMY",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send the order to the server
        logger.info(f"[MT5] Sending {action} {lot_size} lots on {symbol} at {price} (Dev: {deviation})")
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
            "comment": result.comment
        }

    def close_all_positions(self, symbol: Optional[str] = None):
        """Emergency function to liquidate all positions associated with the Sovereign magic number."""
        if not self.connected:
            return

        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            if pos.magic == self.magic_number:
                action = "BUY" if pos.type == 1 else "SELL" # Reverse the position type to close it
                logger.warning(f"[MT5] Liquidating Position {pos.ticket} ({pos.symbol})")
                self.execute_market_order(pos.symbol, action, pos.volume, slippage_pts=50)

    def get_all_positions(self) -> Dict[str, float]:
        """Returns a mapping of {symbol: qty} for all open MT5 positions."""
        if not self.connected:
            return {}

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
            mt5.shutdown()
            logger.info("[MT5] Terminal connection cleanly severed.")
            self.connected = False

MT5Connection = MetaTrader5Agent

class MT5PositionSizer:
    """Institutional Position Sizer for MetaTrader 5."""
    def __init__(self, conn: Optional[MetaTrader5Agent] = None, risk_per_trade: float = 0.01):
        self._conn = conn
        self.risk_per_trade = risk_per_trade

    def calculate_lots(self, balance: float, stop_loss_pips: float, symbol: str) -> float:
        """Calculates lot size based on risk and stop loss. Institutional Single Order Routing."""
        import inspect
        AUTHORIZED_CALLERS = {"_place_mt5_order", "sovereign_decision_engine", "initiate_trade_lifecycle", "flat_all_positions", "repair_state", "run"}
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        if caller_name not in AUTHORIZED_CALLERS:
            # Try one more level up if it's an async wrapper
            caller_frame = caller_frame.f_back if caller_frame else None
            caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"

        if caller_name not in AUTHORIZED_CALLERS:
            logger.critical(f"UNAUTHORIZED SIZING ATTEMPT! Caller '{caller_name}' bypassed Sovereign Engine! REJECTING SIZING.")
            return 0.0

        tick_info = mt5.symbol_info(symbol)
        if tick_info is None:
            logger.warning(f"Sizer: Could not fetch symbol info for {symbol}")
            return 0.01 # Safe fallback

        # Risk Amount calculation
        risk_amount = balance * self.risk_per_trade

        # Convert pips to points/value
        # Note: In MT5, TickValue is the value of 1 Lot for 1 Tick movement in Account Currency.
        tick_size = tick_info.trade_tick_size if tick_info.trade_tick_size > 0 else tick_info.point
        tick_val = tick_info.trade_tick_value if tick_info.trade_tick_value > 0 else 1.0

        # Simple proxy: if stop_loss_pips is in actual price distance
        dist = stop_loss_pips
        if dist < tick_info.point:
            return 0.01

        risk_per_lot = (dist / tick_size) * tick_val
        if risk_per_lot <= 0: return 0.01

        lots = risk_amount / risk_per_lot

        # Respect Broker Constraints
        min_lot = tick_info.volume_min
        max_lot = tick_info.volume_max
        step_lot = tick_info.volume_step

        lots = round(lots / step_lot) * step_lot
        lots = max(min_lot, min(max_lot, lots))

        return round(float(lots), 2)

class FTMOComplianceLayer:
    """Enforces FTMO-specific risk boundaries with Prague-based time synchronization."""
    def __init__(self, daily_limit: float = 0.05, total_limit: float = 0.10, max_trades: int = 20):
        self.daily_limit = daily_limit
        self.total_limit = total_limit
        self.max_trades = max_trades

    def check_daily_loss(self, balance: float, pnl: float) -> bool:
        return pnl >= -(self.daily_limit * balance)

    def best_day_rule(self, today_pnl: float, history: list[float]) -> bool:
        """Sovereign Alpha Rule: No single day should exceed 2/3 of total profit (Consistency)."""
        if not history: return True
        return today_pnl <= (0.66 * sum(history))

    def prague_midnight_reset(self) -> bool:
        """Handle daily reset according to Prague timezone (FTMO Standard)."""
        import pytz
        prague_tz = pytz.timezone("Europe/Prague")
        now_prague = datetime.now(prague_tz)
        return now_prague.hour == 0 and now_prague.minute < 5

    def is_trading_allowed(self, account: dict, trade_count: int = 0) -> tuple[bool, str]:
        pnl = account.get("equity", 0) - account.get("balance", 0)
        if not self.check_daily_loss(account.get("balance", 100000), pnl):
            return (False, "Daily loss limit exceeded (FTMO Violation Risk).")
        if trade_count >= self.max_trades:
            return (False, "Overtrading detected: Max daily trades reached.")
        return (True, "Compliance OK.")
