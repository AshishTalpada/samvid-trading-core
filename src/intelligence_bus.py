import json
import logging
import threading
import time
from typing import Any, Callable

import zmq

logger = logging.getLogger(__name__)

class SovereignIntelligenceBus:
    '''
    Ultra-low-latency inter-process communication (IPC) backbone.
    Utilizes ZeroMQ (ZMQ) PUB/SUB sockets to instantly broadcast neural agent
    decisions, hardware sensor readings, and order executions across all
    Sovereign nodes running on the machine (Rust daemons, C++ execution, Python AI).
    '''
    def __init__(self, publish_port: int = 5555, subscribe_port: int = 5556):
        self.context = zmq.Context()

        # Setup Publisher (for broadcasting)
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://127.0.0.1:{publish_port}")

        # Setup Subscriber (for listening)
        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.connect(f"tcp://127.0.0.1:{subscribe_port}")

        self.callbacks: Any = {}
        self.running = False
        self.listener_thread = None

    def start(self):
        self.running = True
        self.listener_thread = threading.Thread(target=self._listen_loop, daemon=True)  # type: ignore
        self.listener_thread.start()  # type: ignore
        logger.info("[BUS] ZeroMQ Intelligence Bus Online.")

    def subscribe(self, topic: str, callback: Callable[[dict], None]):
        '''Subscribe to a specific topic (e.g., 'ALPHA_SIGNAL', 'HARDWARE_ALERT')'''
        self.sub_socket.setsockopt_string(zmq.SUBSCRIBE, topic)
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        self.callbacks[topic].append(callback)
        logger.debug(f"[BUS] Subscribed to topic: {topic}")

    def publish(self, topic: str, payload: dict):
        '''Instantly broadcast a JSON payload to all connected processes.'''
        message = f"{topic} {json.dumps(payload)}"
        self.pub_socket.send_string(message)

    def _listen_loop(self):
        # Use a poller so we can gracefully exit the blocking recv loop
        poller = zmq.Poller()
        poller.register(self.sub_socket, zmq.POLLIN)

        while self.running:
            try:
                socks = dict(poller.poll(timeout=100))
                if self.sub_socket in socks and socks[self.sub_socket] == zmq.POLLIN:
                    message = self.sub_socket.recv_string()
                    topic, json_data = message.split(" ", 1)

                    data = json.loads(json_data)

                    if topic in self.callbacks:
                        for cb in self.callbacks[topic]:
                            try:
                                cb(data)
                            except Exception as e:
                                logger.error(f"[BUS] Callback error on topic {topic}: {e}")
            except Exception as e:
                logger.error(f"[BUS] Listener Loop Error: {e}")
                time.sleep(1)

    def shutdown(self):
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2.0)
        self.pub_socket.close()
        self.sub_socket.close()
        self.context.term()
        logger.info("[BUS] ZeroMQ Intelligence Bus Shutdown successfully.")
