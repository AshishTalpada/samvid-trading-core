import asyncio
import hashlib
import hmac
import json
import logging
import weakref
from collections.abc import Callable
from typing import Any, Dict, List, Optional

import zmq
import zmq.asyncio

from vault import Vault

logger = logging.getLogger("intelligence_bus")

class SharedIntelligenceBus:
    """
    Sovereign Hybrid Intelligence Bus.
    Combines Institutional Priority-Queuing with ZMQ cross-process relay.
    """
    class PriorityQueueWrapper(asyncio.PriorityQueue):
        async def get(self) -> Any:
            priority_tuple = await super().get()
            if isinstance(priority_tuple, tuple) and len(priority_tuple) >= 3:
                return priority_tuple[-1]
            return priority_tuple

    TOPIC_PRIORITIES = {
        "oracle.freeze": 0, "trade.exit": 1, "trade.entry": 2, "trade.vetting": 3,
        "tick.hft": 5, "news.hft": 6, "institutional.flow": 7, "candle.batch": 12,
        "oracle.state": 15, "calibration.update": 20, "macro.impact": 20
    }

    def __init__(self, publish_port: int = 5555, subscribe_port: int = 5556):
        # Local state (Institutional)
        self._subscribers: dict[str, list[weakref.ReferenceType]] = {}
        self._callbacks: dict[str, list[Any]] = {}
        self._callback_workers: dict[int, tuple[Any, asyncio.Task]] = {}
        self._publish_count = 0
        self._tie_breaker = 0
        self._pending_publish_tasks = set()
        self._max_publish_tasks = 50

        # ZMQ state (C-drive)
        self.context = zmq.asyncio.Context()
        self.publish_port = publish_port
        self.subscribe_port = subscribe_port
        self.pub_socket = self.context.socket(zmq.PUB)
        self.sub_socket = self.context.socket(zmq.SUB)
        self.running = False
        self._listen_task: Optional[asyncio.Task] = None

    async def start(self):
        """Starts the ZMQ relay and local workers."""
        try:
            self.pub_socket.bind(f"tcp://127.0.0.1:{self.publish_port}")
            self.sub_socket.connect(f"tcp://127.0.0.1:{self.subscribe_port}")
            self.running = True
            self._listen_task = asyncio.create_task(self._listen_loop())
            logger.info(f"BUS: Hybrid ZMQ/Priority Matrix Online (Pub:{self.publish_port})")
        except Exception as e:
            logger.error(f"BUS: Failed to start ZMQ relay: {e}. Falling back to Local-Only.")
            self.running = True

    def subscribe(self, topic: str, maxsize: int = 100) -> asyncio.Queue:
        q = self.PriorityQueueWrapper(maxsize=maxsize)
        self._subscribers.setdefault(topic, []).append(weakref.ref(q))
        if self.running:
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        return q

    def unsubscribe(self, topic: str, queue: asyncio.Queue):
        if topic in self._subscribers:
            self._subscribers[topic] = [r for r in self._subscribers[topic] if r() is not None and r() is not queue]

    def on(self, topic: str, handler: Callable):
        import inspect
        ref = weakref.WeakMethod(handler) if inspect.ismethod(handler) else weakref.ref(handler)
        self._callbacks.setdefault(topic, []).append(ref)
        
        h_id = id(handler)
        if h_id not in self._callback_workers:
            q = self.PriorityQueueWrapper(maxsize=100)
            worker = asyncio.create_task(self._handler_worker(ref, q))
            self._callback_workers[h_id] = (q, worker)
        
        if self.running:
            self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    async def _handler_worker(self, handler_ref: Any, q: asyncio.Queue):
        while True:
            try:
                payload = await q.get()
                handler = handler_ref() if isinstance(handler_ref, (weakref.WeakMethod, weakref.ReferenceType)) else handler_ref
                if handler is None: break
                if asyncio.iscoroutinefunction(handler): await handler(payload)
                else: handler(payload)
                q.task_done()
            except asyncio.CancelledError: break
            except Exception as e:
                logger.error(f"BUS: Handler error: {e}")
                await asyncio.sleep(0.1)

    async def publish(self, topic: str, payload: Any):
        self._publish_count += 1
        priority = self.TOPIC_PRIORITIES.get(topic, 10)
        self._tie_breaker += 1
        item = (priority, self._tie_breaker, time.monotonic(), payload)

        # 1. ZMQ Broadcast (External)
        if self.running:
            try:
                message = f"{topic} {json.dumps(payload, default=str)}"
                await self.pub_socket.send_string(message)
            except Exception as e:
                logger.debug(f"BUS: ZMQ relay failed: {e}")

        # 2. Local Dispatch (Institutional)
        tasks = []
        # Push to local subscriber queues
        for ref in self._subscribers.get(topic, []):
            q = ref()
            if q:
                try: q.put_nowait(item)
                except asyncio.QueueFull: pass

        # Push to local callback workers
        for ref in self._callbacks.get(topic, []):
            handler = ref()
            if handler:
                h_id = id(handler)
                if h_id in self._callback_workers:
                    q, _ = self._callback_workers[h_id]
                    try: q.put_nowait(item)
                    except asyncio.QueueFull: pass

        if self._publish_count % 1000 == 0: self._prune_dead_references()

    def publish_sync(self, topic: str, payload: Any):
        try:
            loop = asyncio.get_running_loop()
            asyncio.ensure_future(self.publish(topic, payload), loop=loop)
        except RuntimeError:
            pass

    async def _listen_loop(self):
        while self.running:
            try:
                message = await self.sub_socket.recv_string()
                parts = message.split(" ", 1)
                if len(parts) < 2: continue
                topic, json_data = parts
                data = json.loads(json_data)
                
                # Inbound from ZMQ: Dispatch to local listeners (avoid infinite recursion)
                for ref in self._subscribers.get(topic, []):
                    q = ref()
                    if q: q.put_nowait((10, 0, time.monotonic(), data))
            except asyncio.CancelledError: break
            except Exception as e:
                logger.error(f"BUS: ZMQ Listener error: {e}")
                await asyncio.sleep(0.1)

    def _prune_dead_references(self):
        for t in list(self._callbacks.keys()):
            self._callbacks[t] = [r for r in self._callbacks[t] if (isinstance(r, (weakref.WeakMethod, weakref.ReferenceType)) and r() is not None) or not isinstance(r, (weakref.WeakMethod, weakref.ReferenceType))]
        for t in list(self._subscribers.keys()):
            self._subscribers[t] = [r for r in self._subscribers[t] if r() is not None]

    def get_stats(self) -> dict:
        return {
            "topics": {t: len(q) for t, q in self._subscribers.items()},
            "callbacks": {t: len(c) for t, c in self._callbacks.items()},
            "zmq_active": self.running
        }

    async def stop(self):
        self.running = False
        if self._listen_task: self._listen_task.cancel()
        for _q, t in self._callback_workers.values(): t.cancel()
        self.pub_socket.close()
        self.sub_socket.close()
        self.context.term()
        logger.info("BUS: Matrix OFFLINE.")

_bus_instance = None
def get_bus() -> SharedIntelligenceBus:
    global _bus_instance
    if _bus_instance is None: _bus_instance = SharedIntelligenceBus()
    return _bus_instance
