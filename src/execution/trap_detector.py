import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class TrapDetector:
    """
    Detects institutional 'Spoofing' and 'Baiting' maneuvers in the L2 order book.
    Identifies large limit orders that are repeatedly placed and canceled.
    """
    def __init__(self, cancel_threshold_ms: int = 500, spoof_size_multiplier: float = 10.0):
        self.cancel_threshold_ms = cancel_threshold_ms
        self.spoof_size_multiplier = spoof_size_multiplier
        self.recent_cancels: List[Dict] = []

    def log_order_cancel(self, order_id: str, size: float, duration_ms: int, price: float, side: str) -> None:
        """
        Logs a canceled limit order for spoofing analysis.
        """
        self.recent_cancels.append({
            "order_id": order_id,
            "size": size,
            "duration_ms": duration_ms,
            "price": price,
            "side": side
        })

        # Keep window small to prevent memory bloat
        if len(self.recent_cancels) > 1000:
            self.recent_cancels = self.recent_cancels[-500:]

    def analyze_spoofing_risk(self, current_top_size: float, current_price: float, side: str) -> float:
        """
        Analyzes recent cancel behavior to determine if a resting order is likely a trap.
        
        Args:
            current_top_size: The size of the current resting order at top of book.
            current_price: The price of the order.
            side: 'BID' or 'ASK'.
            
        Returns:
            Spoof risk probability (0.0 to 1.0).
        """
        if current_top_size <= 0:
            return 0.0

        # Look for cancellations on the same side, at similar prices, that were very large and short-lived
        spoof_matches = 0
        total_spoofed_size = 0.0

        for cancel in self.recent_cancels:
            if cancel["side"] == side and cancel["duration_ms"] < self.cancel_threshold_ms:
                # If the canceled order was suspiciously large
                if cancel["size"] > current_top_size * self.spoof_size_multiplier:
                    price_diff_pct = abs(cancel["price"] - current_price) / current_price
                    # If it happened within 10 bps of current price
                    if price_diff_pct < 0.001:
                        spoof_matches += 1
                        total_spoofed_size += cancel["size"]

        if spoof_matches >= 3:
            logger.warning(f"Spoofing trap detected on {side}! {spoof_matches} rapid massive cancels observed.")
            return min(1.0, spoof_matches / 10.0)

        return 0.0
