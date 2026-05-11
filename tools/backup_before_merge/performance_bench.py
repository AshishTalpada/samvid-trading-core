"""
src/performance_bench.py — Sovereign HFT Performance Benchmark

A standalone diagnostic tool to measure the latency improvements
introduced by the Numba JIT compiler and the Async Tick Batcher.

Usage:
    python src/performance_bench.py
"""

import asyncio
import logging
import time
from typing import Any, cast

import numpy as np

# Configure basic logging for the benchmarker
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("PerfBench")


def _generate_synthetic_price_data(n: int = 100_000) -> np.ndarray:
    """Generates synthetic random walk price data."""
    returns = np.random.normal(0, 0.001, n)
    prices = 100.0 * np.exp(np.cumsum(returns))
    return prices


def benchmark_jit_math() -> None:
    """Compare Numba JIT vs Pure NumPy on standard indicators."""
    logger.info("Starting JIT Math Benchmark...")

    try:
        from quant_math import NUMBA_AVAILABLE, bollinger_bands, ema_array, rsi_array
        # Cast to Any to suppress 'Not callable' diagnostics from JIT-decorated functions
        bollinger_bands = cast(Any, bollinger_bands)
        ema_array = cast(Any, ema_array)
        rsi_array = cast(Any, rsi_array)
    except ImportError:
        logger.error("quant_math module not found. Run from project root.")
        return

    if not NUMBA_AVAILABLE:
        logger.warning("Numba is NOT installed. These metrics reflect pure NumPy speeds.")
    else:
        logger.info("Numba JIT is ACTIVE.")

    prices = _generate_synthetic_price_data(100_000)

    # 1. Warmup (compile Numba kernels)
    logger.info("Warming up JIT kernels...")
    _ = ema_array(prices[:100], 14)
    _ = rsi_array(prices[:100], 14)
    _ = bollinger_bands(prices[:100], 20, 2.0)

    # 2. Benchmark EMA
    t0 = time.perf_counter()
    _ = ema_array(prices, 14)
    t_ema = (time.perf_counter() - t0) * 1000

    # 3. Benchmark RSI
    t0 = time.perf_counter()
    _ = rsi_array(prices, 14)
    t_rsi = (time.perf_counter() - t0) * 1000

    # 4. Benchmark Bollinger Bands
    t0 = time.perf_counter()
    _ = bollinger_bands(prices, 20, 2.0)
    t_bb = (time.perf_counter() - t0) * 1000

    print("\n" + "=" * 40)
    print(" Numba JIT Performance (100,000 bars)")
    print("=" * 40)
    print(f" EMA (14):            {t_ema:.2f} ms")
    print(f" RSI (14):            {t_rsi:.2f} ms")
    print(f" Bollinger Bands:     {t_bb:.2f} ms")
    print("=" * 40 + "\n")


async def benchmark_tick_batcher() -> None:
    """Measure the throughput and latency of the TickBatcher."""
    logger.info("Starting TickBatcher Benchmark...")

    try:
        from intelligence_bus import SharedIntelligenceBus
        from tick_batcher import TICK_BATCHER
    except ImportError:
        logger.error("tick_batcher module not found.")
        return

    bus = SharedIntelligenceBus()

    # Metrics
    metrics = {"batches_received": 0, "total_ticks_processed": 0, "latencies": []}

    async def _on_batch(data: dict[str, Any]) -> None:
        metrics["batches_received"] += 1  # type: ignore
        metrics["total_ticks_processed"] += data.get("count", 0)
        ts_last = data.get("ts", time.monotonic())
        latency = (time.monotonic() - ts_last) * 1000
        metrics["latencies"].append(latency)  # type: ignore

    bus.on("tick.batch", _on_batch)

    # Start bus dispatch loop if it has one (or mock it)
    dispatch_task = None
    if hasattr(bus, "run_dispatch_loop"):
        dispatch_task = asyncio.create_task(bus.run_dispatch_loop())

    # Start batcher background task (10ms flush for the test to see more batches)
    TICK_BATCHER._interval = 0.010
    batcher_task = asyncio.create_task(TICK_BATCHER.run(bus))

    # Simulate a high-frequency tick burst (e.g., market open)
    logger.info("Injecting 50,000 synthetic ticks at 100kHz...")

    symbol = "SPY"
    t_start = time.perf_counter()

    for i in range(50_000):
        # Push raw ticks into the batcher (simulating ibkr_streamer)
        TICK_BATCHER.push(symbol, price=500.0 + (i * 0.01), bid=499.9, ask=500.1, size=100)

        # Yield to event loop to allow batcher to flush
        if i % 5000 == 0:
            await asyncio.sleep(0.01)

    # Wait for final flush
    await asyncio.sleep(0.2)
    t_total = time.perf_counter() - t_start

    batcher_task.cancel()
    if dispatch_task:
        dispatch_task.cancel()

    stats = TICK_BATCHER.stats
    batches = stats.get("flush_count", 0)

    print("=" * 40)
    print(" TickBatcher Performance (10ms flush)")
    print("=" * 40)
    print(" Total Ticks Injected:  50,000")
    print(f" Total Time:            {t_total:.2f} s")
    print(f" Throughput:            {50_000 / t_total:,.0f} ticks/sec")
    print(f" Batches Emitted:       {batches}")
    print(f" Compression Ratio:     {50_000 / max(1, batches):.0f}x CPU reduction")
    print("=" * 40 + "\n")


if __name__ == "__main__":
    benchmark_jit_math()
    asyncio.run(benchmark_tick_batcher())
