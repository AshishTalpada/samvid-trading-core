"""
src/market_simulator.py — Sovereign HFT Market Simulator

Injects synthetic high-frequency ticks and order responses into the Intelligence Bus.
Used to validate the Dead Letter Queue, Circuit Breaker, and Order Throttler
without risking real capital on an exchange.

Usage:
    python src/market_simulator.py
"""

import asyncio
import logging
import random
import time

from intelligence_bus import SharedIntelligenceBus
from risk_invariants import ORDER_THROTTLER, RiskInvariants
from tick_batcher import TICK_BATCHER

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
logger = logging.getLogger("Simulator")


async def simulate_flash_crash(bus: SharedIntelligenceBus) -> None:
    """Simulate a flash crash to test order throttling and risk gates."""
    symbol = "SPY"
    logger.info(f"🚨 Simulating Flash Crash for {symbol}...")

    price = 500.0
    for i in range(200):
        # Price drops rapidly, spread widens
        price -= random.uniform(0.1, 1.0)
        spread = random.uniform(0.05, 0.5)

        # Bypass stream and go straight to batcher
        TICK_BATCHER.push(symbol, price, price - spread, price + spread, 500)

        # Attempt to fire an execution signal every tick (which should be throttled)
        if i % 5 == 0:
            is_safe = True
            reason = ""

            if not ORDER_THROTTLER.can_submit():
                is_safe = False
                reason = "THROTTLE_VETO: Rate limit exceeded."
            elif not RiskInvariants.check_notional(symbol, 100, price):
                is_safe = False
                reason = f"NOTIONAL_VETO: {symbol} order exceeds hard cap."

            if is_safe:
                logger.warning(f"  ❌ Order allowed: SELL 100 {symbol} @ {price:.2f}")
            else:
                logger.info(f"  🛡️ Order Blocked: {reason}")

        await asyncio.sleep(0.01)


async def simulate_broker_outage() -> None:
    """Test the Dead Letter Queue by simulating 100% order failure."""
    from resilience_layer import DEAD_LETTER_QUEUE

    logger.info("\n🔌 Simulating Broker Outage (Testing DLQ)...")

    # Mock order execution function that always fails
    async def failing_order_execution(symbol: str, direction: str, shares: int, price: float) -> bool:
        logger.error(f"  Mock Broker: Connection Refused for {direction} {symbol}")
        raise ConnectionError("Broker API timeout")

    # Start the DLQ worker in the background
    worker = asyncio.create_task(DEAD_LETTER_QUEUE.run(retry_fn=failing_order_execution))

    # Enqueue a failed order
    DEAD_LETTER_QUEUE.enqueue("QQQ", "BUY", 50, 400.0, reason="Initial timeout")

    # Wait for the DLQ to exhaust its retries (1s + 2s + 4s = 7s)
    logger.info("  Waiting for DLQ to exhaust retries (approx 7 seconds)...")
    await asyncio.sleep(8.0)

    worker.cancel()

    stats = DEAD_LETTER_QUEUE.stats
    logger.info(f"DLQ Stats: {stats}")
    if stats["escalations"] > 0:
        logger.info("✅ SUCCESS: DLQ properly escalated to TradingState.HALTED.")
    else:
        logger.warning("❌ FAILED: DLQ did not escalate.")


async def main():
    bus = SharedIntelligenceBus()

    # Start batcher
    batcher_task = asyncio.create_task(TICK_BATCHER.run(bus))

    await simulate_flash_crash(bus)
    await simulate_broker_outage()

    batcher_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
