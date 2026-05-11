import logging
import time
from typing import Any, Dict, Optional

import MetaTrader5 as mt5_raw

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
        Executes a direct market order.
        Action must be 'BUY' or 'SELL'.
        """
        if not self.connected:
            return {"status": "error", "message": "MT5 Terminal not connected"}

        if not mt5.symbol_select(symbol, True):
            logger.error(f"[MT5] Failed to select symbol {symbol}")
            return {"status": "error", "message": "Symbol selection failed"}

        tick = self.get_tick(symbol)
        if not tick:
            return {"status": "error", "message": "Pricing unavailable"}

        # Define MT5 Request Dictionary
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        price = tick["ask"] if action == "BUY" else tick["bid"]

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "deviation": slippage_pts,
            "magic": self.magic_number,
            "comment": "Sovereign AI Exec",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Send the order to the server
        logger.info(f"[MT5] Sending {action} {lot_size} lots on {symbol} at {price}")
        result = mt5.order_send(request)

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed, retcode={result.retcode}"
            logger.error(f"[MT5] {error_msg}")
            return {"status": "rejected", "message": error_msg, "retcode": result.retcode}

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
    def __init__(self, risk_per_trade: float = 0.01):
        self.risk_per_trade = risk_per_trade

    def calculate_lots(self, balance: float, stop_loss_pips: float, symbol: str) -> float:
        """Calculates lot size based on risk and stop loss."""
        if stop_loss_pips <= 0:
            return 0.01

        # Simple lot calculation (1.0 lot = $10 per pip for EURUSD)
        # In a real system, we would use symbol_info to get tick_value
        risk_amount = balance * self.risk_per_trade
        lots = risk_amount / (stop_loss_pips * 10.0)
        return round(max(0.01, lots), 2)

class FTMOComplianceLayer:
    """Enforces FTMO-specific risk boundaries."""
    def __init__(self, daily_loss_limit_pct: float = 0.05, total_loss_limit_pct: float = 0.10):
        self.daily_limit = daily_loss_limit_pct
        self.total_limit = total_loss_limit_pct

    def validate_trade(self, current_balance: float, current_equity: float, trade_size: float) -> bool:
        """Checks if a trade would violate FTMO drawdown rules."""
        # Simple check: if equity is below limits, block trade
        drawdown = (current_balance - current_equity) / current_balance
        if drawdown > self.daily_limit:
            logger.critical(f"[FTMO] Daily loss limit exceeded! Current Drawdown: {drawdown*100:.2f}%")
            return False
        return True
