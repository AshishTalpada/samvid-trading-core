"""
src/process_manager.py — CPU-Isolated Process Architecture
Splits the system into three OS processes, each pinned to its own CPU core.

Process 0 — STREAMER (Core 0):  ibkr_streamer + TickBatcher (pure I/O, never blocked)
Process 1 — BRAIN   (Core 1):  All Agents + decision logic
Process 2 — EXECUTOR (Core 2): agent_c_ibkr order routing (listens for signal.execute)

IPC channel: multiprocessing.Queue wrapped as a lightweight publish/subscribe bus.

Usage in main.py:
    from process_manager import ProcessManager
    # Add --multiprocess flag to main.py's argparse
    if args.multiprocess:
        pm = ProcessManager()
        pm.start_all()
        pm.wait()

Note: Default single-process mode is unchanged. This is opt-in.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import signal
import sys
import time
from typing import Any, Callable

logger = logging.getLogger("ProcessManager")


# ── IPC Message ───────────────────────────────────────────────────────────────


class IpcMessage:
    __slots__ = ("topic", "payload", "ts")

    def __init__(self, topic: str, payload: Any):
        self.topic = topic
        self.payload = payload
        self.ts = time.monotonic()


# ── IPC Bus (multiprocessing-safe) ────────────────────────────────────────────


class IpcBus:
    """
    Wraps a multiprocessing.Queue with the same publish/subscribe API
    as SharedIntelligenceBus so existing code needs minimal changes.

    Each process gets its own IpcBus pointed at the shared Queue.
    """

    def __init__(self, queue: "mp.Queue[IpcMessage]", maxsize: int = 10_000):
        self._q = queue
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, topic: str, handler: Callable) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    def publish_sync(self, topic: str, payload: Any) -> None:
        """Non-async publish — safe to call from any thread."""
        try:
            self._q.put_nowait(IpcMessage(topic, payload))
        except Exception as exc:
            logger.warning("IpcBus: failed to publish topic '%s': %s", topic, exc)

    async def publish(self, topic: str, payload: Any) -> None:
        self.publish_sync(topic, payload)

    def drain_one(self, timeout: float = 0.01) -> IpcMessage | None:
        """Pull one message from the queue (blocking up to timeout seconds)."""
        try:
            return self._q.get(timeout=timeout)
        except Exception:
            return None

    async def dispatch_loop(self) -> None:
        """asyncio coroutine: drain queue and invoke local handlers."""
        import asyncio

        while True:
            msg = self.drain_one(timeout=0.001)
            if msg is None:
                await asyncio.sleep(0.005)
                continue
            handlers = self._handlers.get(msg.topic, [])
            for h in handlers:
                try:
                    result = h(msg.payload)
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    logger.error(f"IpcBus: handler error on '{msg.topic}': {e}")


# ── Worker entrypoints ────────────────────────────────────────────────────────


def _pin_to_core(core: int) -> None:
    """Pin current process to a specific CPU core (Linux/Windows)."""
    try:
        p = mp.current_process()
        if sys.platform == "win32":
            import ctypes

            mask = 1 << core
            ctypes.windll.kernel32.SetProcessAffinityMask(  # type: ignore
                ctypes.windll.kernel32.GetCurrentProcess(),
                mask,  # type: ignore
            )
        else:
            os.sched_setaffinity(0, {core})
        logger.info(f"ProcessManager: '{p.name}' pinned to core {core}")
    except Exception as e:
        logger.warning(f"ProcessManager: Core pinning failed (non-fatal): {e}")


def streamer_worker(q_out: "mp.Queue[IpcMessage]", symbols: list[str], config: dict) -> None:
    """
    Process 0 — STREAMER
    Runs ibkr_streamer + TickBatcher. Publishes tick.batch → q_out.
    """
    _pin_to_core(0)
    import asyncio

    from tick_batcher import TICK_BATCHER

    bus = IpcBus(q_out)

    async def _main() -> None:
        try:
            from ibkr_streamer import IBKRStreamer

            streamer = IBKRStreamer(
                host=config.get("ibkr_host", "localhost"),
                port=config.get("ibkr_port", 4002),
                client_id=config.get("client_id", 99),
                bus=None,  # raw ticks go to TICK_BATCHER, not bus
            )
            batcher_task = asyncio.create_task(TICK_BATCHER.run(bus))
            await streamer.run(symbols)
            batcher_task.cancel()
        except Exception as e:
            logger.critical(f"STREAMER process fatal: {e}")

    asyncio.run(_main())


def brain_worker(q_in: "mp.Queue[IpcMessage]", q_out: "mp.Queue[IpcMessage]", config: dict) -> None:
    """
    Process 1 — BRAIN
    Runs all Agents + decision logic. Reads from q_in, writes signals to q_out.
    """
    _pin_to_core(1)
    import asyncio

    bus_in = IpcBus(q_in)
    _bus_out = IpcBus(q_out)

    async def _main() -> None:
        try:
            from quant_math import warmup

            warmup()

            # Brain subscribes to tick.batch from streamer
            dispatch_task = asyncio.create_task(bus_in.dispatch_loop())
            # Brain publishes signal.execute → executor process via bus_out
            # (Brain init omitted here — integrate with existing TradingBrain)
            await dispatch_task
        except Exception as e:
            logger.critical(f"BRAIN process fatal: {e}")

    asyncio.run(_main())


def executor_worker(q_in: "mp.Queue[IpcMessage]", config: dict) -> None:
    """
    Process 2 — EXECUTOR
    Listens for signal.execute events and routes orders via agent_c_ibkr.
    Completely isolated — IBKR connection latency cannot block the Brain.
    """
    _pin_to_core(2)
    import asyncio

    bus = IpcBus(q_in)

    async def _on_signal(payload: dict) -> None:
        """Route an execution signal to IBKR."""
        try:
            symbol = payload.get("symbol")
            direction = payload.get("direction")
            shares = payload.get("shares", 0)
            price = payload.get("price", 0.0)
            logger.info(f"EXECUTOR: Received signal {direction} {shares}x {symbol} @ {price:.2f}")
            # Hook into existing agent_c_ibkr here
        except Exception as e:
            logger.error(f"EXECUTOR: Signal handling error: {e}")

    bus.subscribe("signal.execute", lambda p: asyncio.ensure_future(_on_signal(p)))

    async def _main() -> None:
        await bus.dispatch_loop()

    asyncio.run(_main())


# ── ProcessManager ────────────────────────────────────────────────────────────


class ProcessManager:
    """
    Spawns and manages the three isolated trading processes.
    Handles graceful shutdown on SIGINT/SIGTERM.
    """

    def __init__(self, symbols: list[str] | None = None, config: dict | None = None):
        self._symbols = symbols or []
        self._config = config or {}
        self._procs: list[mp.Process] = []

        # Shared inter-process queues
        self._q_stream_brain: "mp.Queue[IpcMessage]" = mp.Queue(maxsize=20_000)
        self._q_brain_exec: "mp.Queue[IpcMessage]" = mp.Queue(maxsize=5_000)

    def start_all(self) -> None:
        """Spawn all three processes."""
        procs = [
            mp.Process(
                target=streamer_worker,
                args=(self._q_stream_brain, self._symbols, self._config),
                name="SovereignStreamer",
                daemon=True,
            ),
            mp.Process(
                target=brain_worker,
                args=(self._q_stream_brain, self._q_brain_exec, self._config),
                name="SovereignBrain",
                daemon=True,
            ),
            mp.Process(
                target=executor_worker,
                args=(self._q_brain_exec, self._config),
                name="SovereignExecutor",
                daemon=True,
            ),
        ]

        for p in procs:
            p.start()
            logger.info(f"ProcessManager: Spawned '{p.name}' (PID {p.pid})")
            self._procs.append(p)

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def wait(self) -> None:
        """Block until all processes exit."""
        for p in self._procs:
            p.join()

    def _shutdown(self, *_: Any) -> None:
        logger.info("ProcessManager: Shutdown signal received — terminating all processes.")
        for p in self._procs:
            if p.is_alive():
                p.terminate()
        for p in self._procs:
            p.join(timeout=5)
            if p.is_alive():
                p.kill()
        logger.info("ProcessManager: All processes stopped.")

    @property
    def all_alive(self) -> bool:
        return all(p.is_alive() for p in self._procs)
