import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class SmartExecutionRouter:
    """
    Dynamically routes orders across multiple brokerages and dark pools
    to minimize slippage, maximize fill rates, and ensure redundancy.
    If IBKR API fails, immediately fails over to Alpaca or direct FIX links.
    """
    def __init__(self):
        self.brokers = {
            "IBKR": {"latency": 5.0, "status": "ONLINE", "fee_bps": 0.3},
            "ALPACA": {"latency": 25.0, "status": "ONLINE", "fee_bps": 0.0},
            "DARK_POOL": {"latency": 150.0, "status": "ONLINE", "fee_bps": 1.0}
        }
        self.primary = "IBKR"

    def update_broker_health(self, broker: str, latency_ms: float, is_online: bool) -> None:
        if broker in self.brokers:
            self.brokers[broker]["latency"] = latency_ms
            self.brokers[broker]["status"] = "ONLINE" if is_online else "OFFLINE"

    def select_venue(self, order_size_usd: float, urgency: str) -> str:
        online = {k: v for k, v in self.brokers.items() if v["status"] == "ONLINE"}
        if not online:
            logger.critical("[ROUTER] FATAL: All broker connections are OFFLINE.")
            return "NONE"

        if order_size_usd > 1_000_000 and "DARK_POOL" in online:
            return "DARK_POOL"  # Hide massive orders

        if urgency == "HIGH":
            # Sort by lowest latency
            return sorted(online.keys(), key=lambda k: online[k]["latency"])[0]  # type: ignore

        # Sort by lowest fee
        return sorted(online.keys(), key=lambda k: online[k]["fee_bps"])[0]  # type: ignore

    def route_order(self, ticker: str, size: float, urgency: str = "NORMAL") -> str:
        venue = self.select_venue(size * 100, urgency)  # Approximating USD value
        logger.info(f"[ROUTER] Routing {size} {ticker} -> {venue} (Urgency: {urgency})")
        return venue
