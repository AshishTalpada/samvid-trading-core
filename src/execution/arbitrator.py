import logging
import time
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class FIXExecutionReport:
    order_id: str
    exec_id: str
    exec_type: str
    ord_status: str
    symbol: str
    side: str
    fill_qty: float
    fill_price: float
    leaves_qty: float
    cum_qty: float
    transact_time: str
    
    # NBBO at time of fill
    nbbo_bid: float
    nbbo_ask: float

class BrokerArbitrator:
    """
    Advanced Broker Arbitrator for High-Frequency Trading.
    Monitors all inbound FIX ExecutionReports (Tag 35=8).
    Compares Fill Prices against the National Best Bid and Offer (NBBO) at the exact microsecond of execution.
    If a fill is executed outside the NBBO (a predatory or illegal fill under Reg NMS),
    this agent instantly disputes the trade via FIX Tag 35=DK (Don't Know Trade).
    """
    
    # Standard FIX Tag definitions
    TAG_MSG_TYPE = "35"
    TAG_ORDER_ID = "11"
    TAG_EXEC_ID = "17"
    TAG_EXEC_TYPE = "150"
    TAG_ORD_STATUS = "39"
    TAG_SYMBOL = "55"
    TAG_SIDE = "54"
    TAG_FILL_QTY = "32"
    TAG_FILL_PRICE = "31"
    TAG_TEXT = "58"
    
    # Thresholds
    ALLOWED_SLIPPAGE_BPS = 0.5  # 0.5 basis points allowed for market orders
    
    def __init__(self):
        self.active_orders: Dict[str, dict] = {}
        self.disputed_trades: list = []
        self.total_arbitrations_won = 0
        self.total_arbitrations_lost = 0

    def register_order_intent(self, order_id: str, symbol: str, side: str, expected_price: float, qty: float, current_nbbo: tuple):
        """Register our internal expectation of the trade before it goes to the broker."""
        self.active_orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "expected_price": expected_price,
            "qty": qty,
            "expected_nbbo": current_nbbo,  # (Bid, Ask)
            "timestamp": time.time_ns()
        }
        logger.info(f"[ARBITRATOR] Registered Order {order_id} intent for {qty} {symbol} @ {expected_price}")

    def evaluate_fix_execution(self, fix_message: str, current_nbbo: tuple) -> bool:
        """
        Parses a raw FIX message string, extracts the execution details, and arbitrates.
        Returns True if the fill is accepted, False if disputed.
        """
        tags = self._parse_fix_message(fix_message)
        
        msg_type = tags.get(self.TAG_MSG_TYPE)
        if msg_type != "8":
            # Not an ExecutionReport
            return True
            
        ord_status = tags.get(self.TAG_ORD_STATUS)
        if ord_status not in ["1", "2"]:
            # Not a Partial Fill (1) or Filled (2) status
            return True
            
        try:
            report = FIXExecutionReport(
                order_id=tags.get(self.TAG_ORDER_ID, "UNKNOWN"),
                exec_id=tags.get(self.TAG_EXEC_ID, "UNKNOWN"),
                exec_type=tags.get(self.TAG_EXEC_TYPE, ""),
                ord_status=ord_status,
                symbol=tags.get(self.TAG_SYMBOL, "UNKNOWN"),
                side=tags.get(self.TAG_SIDE, "1"),
                fill_qty=float(tags.get(self.TAG_FILL_QTY, 0.0)),
                fill_price=float(tags.get(self.TAG_FILL_PRICE, 0.0)),
                leaves_qty=0.0,
                cum_qty=0.0,
                transact_time=str(time.time_ns()),
                nbbo_bid=current_nbbo[0],
                nbbo_ask=current_nbbo[1]
            )
        except ValueError as e:
            logger.error(f"[ARBITRATOR] Malformed FIX Execution Report: {e}")
            return False

        return self._arbitrate_fill(report)

    def _arbitrate_fill(self, report: FIXExecutionReport) -> bool:
        """Core logic to determine if a fill is fair or predatory."""
        order_intent = self.active_orders.get(report.order_id)
        if not order_intent:
            logger.warning(f"[ARBITRATOR] Received fill for unknown Order ID {report.order_id}. Accepting by default.")
            return True

        expected_price = order_intent["expected_price"]
        side = report.side
        
        # 1: Buy, 2: Sell (FIX Standard)
        is_buy = side == "1"
        
        # Calculate slippage in Basis Points
        if is_buy:
            slippage_bps = ((report.fill_price - expected_price) / expected_price) * 10000
        else:
            slippage_bps = ((expected_price - report.fill_price) / expected_price) * 10000

        logger.debug(f"[ARBITRATOR] Order {report.order_id} filled at {report.fill_price}. Slippage: {slippage_bps:.2f} bps")

        # Reg NMS Check: Was the fill outside the NBBO at the time of execution?
        reg_nms_violation = False
        if is_buy and report.fill_price > report.nbbo_ask:
            reg_nms_violation = True
        elif not is_buy and report.fill_price < report.nbbo_bid:
            reg_nms_violation = True

        if reg_nms_violation:
            logger.critical(f"[ARBITRATOR] REG NMS VIOLATION DETECTED! Fill {report.fill_price} outside NBBO ({report.nbbo_bid} - {report.nbbo_ask})")
            self._dispute_fill(report, "REG NMS TRADE THROUGH VIOLATION")
            return False

        if slippage_bps > self.ALLOWED_SLIPPAGE_BPS:
            logger.critical(f"[ARBITRATOR] Predatory Fill Detected. Slippage {slippage_bps:.2f} bps exceeds allowance of {self.ALLOWED_SLIPPAGE_BPS} bps.")
            self._dispute_fill(report, f"PREDATORY SLIPPAGE: {slippage_bps:.2f} bps")
            return False

        # Clean fill. Remove from active intent tracking if fully filled.
        if report.ord_status == "2":
            del self.active_orders[report.order_id]
            
        return True

    def _dispute_fill(self, report: FIXExecutionReport, reason: str):
        """
        Generates a Don't Know Trade (DK) FIX message to formally dispute the execution 
        with the broker or venue.
        """
        # FIX Tag 35=Q is Don't Know Trade (DK)
        dk_msg = f"8=FIX.4.4|35=Q|11={report.order_id}|17={report.exec_id}|39={report.ord_status}|"
        dk_msg += f"55={report.symbol}|54={report.side}|32={report.fill_qty}|31={report.fill_price}|"
        dk_msg += f"127=OTHER|58={reason}|"
        
        logger.warning(f"[ARBITRATOR] Sending FIX Dispute to Broker: {dk_msg}")
        self.disputed_trades.append({
            "report": report,
            "reason": reason,
            "dk_msg": dk_msg,
            "timestamp": time.time()
        })

    def _parse_fix_message(self, fix_string: str) -> Dict[str, str]:
        """Parses a raw SOH-delimited FIX string into a dictionary."""
        # Note: Usually SOH is \x01, but we use '|' here for readability in logs
        delim = '\x01' if '\x01' in fix_string else '|'
        pairs = fix_string.split(delim)
        
        tags = {}
        for pair in pairs:
            if '=' in pair:
                tag, val = pair.split('=', 1)
                tags[tag] = val
        return tags
