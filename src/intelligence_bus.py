"""
src/intelligence_bus.py — SharedIntelligenceBus
================================================
In-process async pub/sub message bus that wires every trading component
together so they share knowledge simultaneously.
Topics (canonical list):
  "candle.batch"        — DataPipeline finished storing a new batch of bars
                          payload: {"symbols": [...], "count": n, "timestamp": str}
  "oracle.state"        — DhatuOracle published a new global state
                          payload: {"dhatu": str, "action": str, "modifier": float,
                                    "confidence": float, "summary": str}
  "trade.entry"         — Brain opened a new position
                          payload: {"symbol": str, "pattern": str, "entry": float,
                                    "stop": float, "target": float, "qty": int,
                                    "account": str, "regime": str}
  "trade.exit"          — Brain closed a position
                          payload: {"symbol": str, "pattern": str, "outcome": str,
                                    "r_multiple": float, "pnl": float,
                                    "regime": str, "hold_hours": float}
  "calibration.update"  — Agent D updated the expectancy matrix
                          payload: {"n_trades": int, "data_rating": str,
                                    "top_patterns": [{"key": str, "win_rate": float, "avg_r": float}]}
  "sector.alert"        — Agent E detected a sector distribution event
                          payload: {"sector": str, "exposure_pct": float, "action": str}
  "oracle.freeze"       — DhatuOracle emitted an Abhava/Viyoga (hard stop signal)
                          payload: {"dhatu": str, "reason": str}
Design decisions:
  - Fire-and-forget for data events (candle.batch, oracle.state) — no blocking
  - Synchronous acknowledgement NOT required — subscribers must handle lag
  - Per-subscriber asyncio.Queue with maxsize=100 to prevent memory leak on slow consumers
  - Missed events are silently dropped when a subscriber's queue is full
  - Zero external dependencies — pure standard library + asyncio
"""

import asyncio
import hashlib
import hmac
import json
import logging
import weakref
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class SharedIntelligenceBus:
    """
    Lightweight in-process async pub/sub bus.
    Usage:
        bus = SharedIntelligenceBus()
        # Subscribe (returns an asyncio.Queue the caller reads from)
        q = bus.subscribe("candle.batch")
        # ── in a task:
        while True:
            payload = await q.get()
            ...
        # Publish (fire-and-forget, never blocks)
        await bus.publish("candle.batch", {"symbols": ["SPY"], "count": 100})
        # Register async callback (auto-spawned as task on each publish)
        bus.on("oracle.state", my_handler_coroutine)
    """

    def __init__(self) -> None:
        # topic → list of subscriber queues
        self._subscribers: dict[str, list[asyncio.PriorityQueue]] = {}
        # topic → list of async callbacks (spawned as tasks on publish)
        self._callbacks: dict[str, list[Callable]] = {}
        # id(handler) -> (Queue, Task) to prevent task-bombing
        self._callback_workers: dict[int, tuple[Any, asyncio.Task]] = {}
        self._relay_queues: list[asyncio.PriorityQueue] = []
        self._publish_count: int = 0
        self._tie_breaker: int = 0  # Tie-breaker for PriorityQueue comparison

        self._pending_publish_tasks = set()
        self._max_publish_tasks = 50

        self.TOPIC_PRIORITIES = {
            "oracle.freeze": 0,  # Hard Stop (Abhava)
            "trade.exit": 1,  # Portfolio preservation
            "trade.entry": 2,  # Capture opportunity
            "trade.vetting": 3,  # Cognitive load
            "tick.hft": 5,  # 100Hz stream (Pulse)
            "news.hft": 6,  # High-freq news
            "institutional.flow": 7,  # Large size alerts (Impact)
            "candle.batch": 12,  # 1m/5m/1h closures
            "oracle.state": 15,  # Routine updates
            "calibration.update": 20,  # Slow learning
            "macro.impact": 20,  # 15m synthesis
        }

    # Priority Queue Wrapper (Maintains Backward Compatibility)

    class PriorityQueueWrapper(asyncio.PriorityQueue):
        """
        Extends PriorityQueue so 'await q.get()' returns payload, NOT the priority tuple.
        This allows us to swap FIFO with PriorityQueue without breaking the 89 GAPs already coded.
        """

        async def get(self) -> Any:
            priority_tuple = await super().get()
            if isinstance(priority_tuple, tuple) and len(priority_tuple) == 4:
                return priority_tuple[3]
            # Backward compatibility for (priority, ts, payload)
            if isinstance(priority_tuple, tuple) and len(priority_tuple) == 3:
                return priority_tuple[2]
            return priority_tuple

    # Subscribe via Queue (pull model)

    def subscribe(self, topic: str, maxsize: int = 100) -> "asyncio.PriorityQueue[Any]":
        """
        Subscribe to a topic and get a PriorityQueue to read messages from.
        Uses weak references so dead subscribers don't leak memory.
        """
        q = self.PriorityQueueWrapper(maxsize=maxsize)
        # Store a weak reference to the queue
        self._subscribers.setdefault(topic, []).append(weakref.ref(q))
        logger.debug(
            f"BUS: subscribed to '{topic}' (Memory-Safe Queue #{len(self._subscribers[topic])})"
        )
        return q

    def unsubscribe(self, topic: str, queue: "asyncio.PriorityQueue[Any]") -> None:
        """Remove a queue subscription."""
        if topic in self._subscribers:
            # Match by the underlying object the weakref points to
            self._subscribers[topic] = [
                r for r in self._subscribers[topic] if r() is not None and r() is not queue
            ]

    # Subscribe via Callback (push model)

    def on(self, topic: str, handler: Callable) -> None:
        """
        Register a callback for a topic.
        Uses weak references to prevent memory leaks from old/restarted agents.
        """
        # Determine if we should use WeakMethod (for instance methods) or ref (for functions)
        import inspect

        if inspect.ismethod(handler):
            ref = weakref.WeakMethod(handler)
        else:
            try:
                ref = weakref.ref(handler)
            except TypeError:
                # Fallback for things that cannot be weakref'd (rare in this system)
                logger.warning(
                    f"BUS: Handler {handler} cannot be weakref'd. Using strong reference."
                )
                ref = handler

        self._callbacks.setdefault(topic, []).append(ref)

        h_id = id(handler)
        if h_id not in self._callback_workers:
            q = self.PriorityQueueWrapper(maxsize=100)
            worker = asyncio.create_task(self._handler_worker(ref, q))
            self._callback_workers[h_id] = (q, worker)

            def _cleanup_worker(task: asyncio.Task):
                # ONLY cancel the task — this is thread-safe (sets a flag).
                # NEVER touch _callback_workers here; that runs in a GC thread
                # and would race with the event loop. Dead worker cleanup is
                # handled safely by _prune_dead_references in the async loop.
                task.cancel()

            # Target the underlying object to prevent immediate GC of transient bound methods
            target_obj = getattr(handler, "__self__", handler)
            weakref.finalize(target_obj, _cleanup_worker, worker)

        logger.debug(f"BUS: callback registered for '{topic}' (Memory-Safe Matrix ONLINE)")

    def _prune_dead_references(self) -> None:
        """Remove callbacks and subscribers whose owners have been garbage collected."""
        # 1. Prune Callbacks
        for topic in list(self._callbacks.keys()):
            self._callbacks[topic] = [
                r
                for r in self._callbacks[topic]
                if (isinstance(r, (weakref.WeakMethod, weakref.ReferenceType)) and r() is not None)
                or not isinstance(r, (weakref.WeakMethod, weakref.ReferenceType))
            ]
            if not self._callbacks[topic]:
                del self._callbacks[topic]

        # 2. Prune Subscribers (Queues)
        for topic in list(self._subscribers.keys()):
            self._subscribers[topic] = [
                r
                for r in self._subscribers[topic]
                if isinstance(r, weakref.ReferenceType) and r() is not None
            ]
            if not self._subscribers[topic]:
                del self._subscribers[topic]

        # 3. Prune Callback Workers (runs in event loop — thread-safe)
        dead_workers = [
            hid
            for hid, (_, task) in list(self._callback_workers.items())
            if task.done() or task.cancelled()
        ]
        for hid in dead_workers:
            self._callback_workers.pop(hid, None)
        if dead_workers:
            logger.debug(
                f"BUS: Pruned {len(dead_workers)} dead callback worker(s)"
            )

    async def _handler_worker(self, handler_ref: Any, q: asyncio.PriorityQueue) -> None:
        """Dedicated worker for a callback handler to prevent task-bombing."""
        while True:
            try:
                payload = await q.get()

                handler = (
                    handler_ref()
                    if isinstance(handler_ref, (weakref.WeakMethod, weakref.ReferenceType))
                    else handler_ref
                )

                if handler is None:
                    logger.debug("BUS: Handler collected by GC. Terminating worker.")
                    q.task_done()
                    break

                await handler(payload)
                q.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Get name safely for logging
                # Check for .__name__ or .__class__.__name__ or str()
                h_name = getattr(handler_ref, "__name__", "unknown_handler")
                logger.error(f"BUS: handler {h_name} raised error: {e}")
                await asyncio.sleep(0.1)  # Cool down

    def off(self, topic: str, handler: Callable) -> None:
        """Remove an async callback."""
        if topic not in self._callbacks:
            return
        # _callbacks stores weak references, not raw handlers.
        # We must find and remove the weak ref that points to handler.
        refs = self._callbacks[topic]
        to_remove = None
        for r in refs:
            pointed = r() if isinstance(r, (weakref.WeakMethod, weakref.ReferenceType)) else r
            if pointed is handler:
                to_remove = r
                break
        if to_remove is not None:
            refs.remove(to_remove)
        if not refs:
            del self._callbacks[topic]

    # Publish

    def _on_publish_task_done(self, task: asyncio.Task) -> None:
        """Cleanup finished publish tasks from the tracker."""
        self._pending_publish_tasks.discard(task)

    async def _publish_with_concurrency(self, topic: str, p_item: tuple, r_item: tuple) -> None:
        """Internal publish implementation with event delivery."""
        # 1. Push to all queued subscribers
        for ref in list(self._subscribers.get(topic, [])):
            q = ref() if isinstance(ref, weakref.ReferenceType) else ref
            if q:
                try:
                    q.put_nowait(p_item)
                except (asyncio.QueueFull, Exception) as e:
                    logger.debug("IntelligenceBus: subscriber queue full or error for topic %s: %s", topic, e)

        # 2. Push to wildcard relay queues
        for q in list(self._relay_queues):
            try:
                q.put_nowait(r_item)
            except (asyncio.QueueFull, Exception) as e:
                logger.debug("IntelligenceBus: relay queue full or error for topic %s: %s", topic, e)

        # 3. Push to callback workers
        for ref in self._callbacks.get(topic, []):
            handler = ref() if isinstance(ref, (weakref.WeakMethod, weakref.ReferenceType)) else ref
            if handler:
                h_id = id(handler)
                if h_id in self._callback_workers:
                    q, _ = self._callback_workers[h_id]
                    try:
                        q.put_nowait(p_item)
                    except asyncio.QueueFull as e:
                        logger.debug("IntelligenceBus: callback worker queue full for topic %s: %s", topic, e)

    async def publish(self, topic: str, payload: Any = None) -> None:
        self._publish_count += 1

        # Determine Priority (0=Urgent, 10=Normal)
        priority = self.TOPIC_PRIORITIES.get(topic, 10)

        # Capture timestamp to ensure FIFO for equal priority (Pillar 12 safety)
        from time import monotonic

        ts = monotonic()

        # Envelope for PriorityQueue matching: (priority, counter, ts, payload)
        self._tie_breaker += 1
        p_item = (priority, self._tie_breaker, ts, payload)

        # Envelope for wildcard relay
        envelope = {"topic": topic, "payload": payload}
        r_item = (priority, self._tie_breaker, ts, envelope)

        await asyncio.sleep(0)

        if priority <= 2:
            logger.info(f" BUS PRIORITY [{priority}]: {topic}")
        else:
            logger.debug(f" BUS EVENT: {topic} (P{priority})")

        # Periodic Pruning (every 1000 messages)
        if self._publish_count % 1000 == 0:
            self._prune_dead_references()

        # Check concurrency before spawning a delivery task
        if len(self._pending_publish_tasks) >= self._max_publish_tasks:
            # Low-priority drop to preserve event loop health
            if priority >= 10:
                return
            else:
                # High-priority: run synchronously but briefly
                await self._publish_with_concurrency(topic, p_item, r_item)
                return

        task = asyncio.create_task(self._publish_with_concurrency(topic, p_item, r_item))
        self._pending_publish_tasks.add(task)
        task.add_done_callback(self._on_publish_task_done)

    def publish_sync(self, topic: str, payload: Any = None) -> None:
        """
        Synchronous version of publish — used from non-async contexts.
        Schedules the publish on the running event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(self.publish(topic, payload), loop=loop)
        except RuntimeError:
            # No running loop — try get_event_loop fallback
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.run_until_complete(self.publish(topic, payload))
            except Exception:
                pass  # System not yet started — silently skip

    # Diagnostics

    async def start_socket_relay(self, host: str = "127.0.0.1", port: int = 5570) -> None:
        """
        Opens a TCP socket to mirror in-process events to external observers
        and receive external intelligence injections.
        """
        logger.info(f"BUS: Starting Node Relay on {host}:{port}...")

        try:
            server = await asyncio.start_server(self._handle_node_connection, host, port)
            async with server:
                await server.serve_forever()
        except Exception as e:
            logger.error(f"BUS: Node Relay Error: {e}")

    async def _handle_node_connection(self, reader, writer) -> None:
        """
        Handle an incoming external Mind connection with mandatory authentication.
        Mandatory HMAC Handshake before relay begins.
        """
        addr = writer.get_extra_info("peername")
        from vault import Vault

        # 1. AUTHENTICATION HANDSHAKE
        server_key = Vault.get("API_SERVER_KEY")
        if not server_key:
            logger.error("BUS: No API_SERVER_KEY found in Vault. Refusing node relay.")
            writer.close()
            return

        try:
            # Expect first line to be the auth token
            # payload: {"topic": "auth", "token": "HMAC_HEX"}
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            if not line:
                return

            auth_msg = json.loads(line.decode())
            if auth_msg.get("topic") != "auth":
                logger.warning(f"BUS: Peer {addr} failed auth sequence (Incorrect topic).")
                writer.close()
                return

            token = auth_msg.get("token", "")

            # Verify HMAC-SHA256 of current 30s window timestamp
            from time_sync import TimeSync

            ts = int(TimeSync.now().timestamp()) // 30
            valid_auth = False
            for offset in (0, -1, 1):  # Standard +/- 30s window
                msg = str(ts + offset).encode()
                expected = hmac.new(server_key.encode(), msg, hashlib.sha256).hexdigest()
                if hmac.compare_digest(token, expected):
                    valid_auth = True
                    break

            if not valid_auth:
                logger.warning(f"BUS: Peer {addr} provided INVALID AUTH TOKEN. Disconnecting.")
                writer.close()
                return

            logger.info(f"BUS: External Mind {addr} AUTHENTICATED successfully.")

        except asyncio.TimeoutError:
            logger.warning(f"BUS: Peer {addr} timed out during auth handshake.")
            writer.close()
            return
        except Exception as e:
            logger.error(f"BUS: Auth failure for {addr}: {e}")
            writer.close()
            return

        # 2. Spawn a task to relay local events TO the external mind
        relay_task = asyncio.create_task(self._relay_to_node(writer))

        try:
            # 3. Receive events FROM the external mind
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    msg = json.loads(data.decode())
                    topic = msg.get("topic")
                    payload = msg.get("payload")
                    if topic:
                        # Inject external intelligence into the local bus
                        await self.publish(topic, payload)
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"BUS: External Mind {addr} disconnected: {e}")
        finally:
            relay_task.cancel()
            writer.close()
            await writer.wait_closed()

    async def _relay_to_node(self, writer) -> None:
        """Relays all local BUS events to the connected external mind."""
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._relay_queues = getattr(self, "_relay_queues", [])
        self._relay_queues.append(q)

        def _safe_serialize(obj):
            """Robust JSON serialization that handles complex broker objects and non-serializable types."""
            import decimal
            from datetime import date, datetime

            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            # Handle numpy scalars (numpy.bool_, numpy.int64, numpy.float64, etc.)
            # These are NOT handled by json.dumps natively and cause TypeError.
            try:
                import numpy as np

                if isinstance(obj, np.bool_):
                    return bool(obj)
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
            except ImportError as e:
                logger.debug("IntelligenceBus: numpy not available for JSON serialization: %s", e)
            if hasattr(obj, "to_dict"):
                return obj.to_dict()
            if hasattr(obj, "__dict__"):
                # Handle generic objects by converting their __dict__ (Surgical conversion)
                return {
                    k: _safe_serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")
                }
            return str(obj)

        try:
            while True:
                envelope = await q.get()
                try:
                    # Use the safe serializer for the payload
                    serialized = json.dumps(envelope, default=_safe_serialize)
                    writer.write(serialized.encode() + b"\n")
                    await writer.drain()
                except Exception as e:
                    logger.warning(f"BUS: Relay serialization error: {e}")
                    continue
        except Exception as _relay_err:
            logger.debug(f"BUS: Relay loop ended with error (non-critical): {_relay_err}")
        finally:
            if q in self._relay_queues:
                self._relay_queues.remove(q)

    def get_stats(self) -> dict[str, Any]:
        """Return bus statistics for telemetry."""
        return {
            "topics": {topic: len(queues) for topic, queues in self._subscribers.items()},
            "callbacks": {topic: len(cbs) for topic, cbs in self._callbacks.items()},
            "pending_publish_tasks": len(self._pending_publish_tasks),
        }

    async def stop(self) -> None:
        """Sovereign Shutdown: Terminates all callback workers and pending tasks."""
        logger.info("SharedIntelligenceBus: Shutting down matrix...")

        # 1. Cancel callback workers
        for _q, task in list(self._callback_workers.values()):
            task.cancel()

        # 2. Cancel pending publish tasks
        for task in list(self._pending_publish_tasks):
            if not task.done():
                task.cancel()

        if self._pending_publish_tasks:
            await asyncio.gather(*self._pending_publish_tasks, return_exceptions=True)

        # Clear dictionary and pending tasks
        self._callback_workers = {}
        self._pending_publish_tasks.clear()
        logger.info("SharedIntelligenceBus: Matrix OFFLINE.")


_bus: SharedIntelligenceBus | None = None
import threading

_bus_lock = threading.Lock()


def get_bus() -> SharedIntelligenceBus:
    """
    Get (or lazily create) the global SharedIntelligenceBus singleton.
    Always returns the same instance within a process (Thread-Safe).
    """
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = SharedIntelligenceBus()
                logger.info("SharedIntelligenceBus: singleton created")
    return _bus


def set_bus(bus: SharedIntelligenceBus) -> None:
    """Inject a pre-created bus (used in main.py to ensure single instance)."""
    global _bus
    _bus = bus
