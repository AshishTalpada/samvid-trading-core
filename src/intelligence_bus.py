import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)

class SharedIntelligenceBus:
    """
    PILLAR 2: Ultra-low-latency async inter-process communication (IPC) backbone.
    Utilizes ZeroMQ (ZMQ) PUB/SUB sockets with asyncio integration.
    """
    def __init__(self, publish_port: int = 5555, subscribe_port: int = 5556):
        self.context = zmq.asyncio.Context()
        self.publish_port = publish_port
        self.subscribe_port = subscribe_port

        self.pub_socket = self.context.socket(zmq.PUB)
        self.sub_socket = self.context.socket(zmq.SUB)

        self.queues: Dict[str, List[asyncio.Queue]] = {}
        self.running = False
        self._listen_task: Optional[asyncio.Task] = None

    async def start(self):
        """Starts the async listener loop."""
        self.pub_socket.bind(f"tcp://127.0.0.1:{self.publish_port}")
        self.sub_socket.connect(f"tcp://127.0.0.1:{self.subscribe_port}")

        self.running = True
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info(f"[BUS] Async ZeroMQ Intelligence Bus Online (Pub:{self.publish_port}, Sub:{self.subscribe_port})")

    def subscribe(self, topic: str, maxsize: int = 100) -> asyncio.Queue:
        """
        Subscribe to a topic and return an asyncio.Queue.
        PILLAR 2: Event-driven routing.
        """
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        q = asyncio.Queue(maxsize=maxsize)
        if topic not in self.queues:
            self.queues[topic] = []
        self.queues[topic].append(q)
        logger.debug(f"[BUS] Subscribed to topic: {topic}")
        return q

    def on(self, topic: str, callback: Any):
        """
        Legacy Bridge: Registers a callback for a specific topic.
        Internally uses the queue-based system.
        """
        q = self.subscribe(topic)

        async def _callback_wrapper():
            while self.running:
                try:
                    data = await q.get()
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"[BUS] Callback Error for {topic}: {e}")

        asyncio.create_task(_callback_wrapper())

    async def publish(self, topic: str, payload: dict):
        """Broadcasts a JSON payload to all subscribers."""
        try:
            message = f"{topic} {json.dumps(payload)}"
            await self.pub_socket.send_string(message)
        except Exception as e:
            logger.error(f"[BUS] Publish failed: {e}")

    async def _listen_loop(self):
        """Main async listener loop."""
        while self.running:
            try:
                message = await self.sub_socket.recv_string()
                parts = message.split(" ", 1)
                if len(parts) < 2:
                    continue

                topic, json_data = parts
                data = json.loads(json_data)

                if topic in self.queues:
                    for q in self.queues[topic]:
                        if q.full():
                            # Drop oldest if full to maintain HFT speed
                            try:
                                q.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        await q.put(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[BUS] Listener Error: {e}")
                await asyncio.sleep(0.1)

    async def stop(self):
        """Shuts down the bus and cleans up sockets."""
        self.running = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        self.pub_socket.close()
        self.sub_socket.close()
        self.context.term()
        logger.info("[BUS] ZeroMQ Intelligence Bus Shutdown successfully.")

_bus_instance = None

def get_bus() -> SharedIntelligenceBus:
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = SharedIntelligenceBus()
    return _bus_instance
