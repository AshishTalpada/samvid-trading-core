import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


class QuantumEntanglementBus:
    """
    Simulated Quantum Entanglement Communication Bus.
    In a post-quantum communications environment, this would interface with
    Quantum Key Distribution (QKD) hardware to exchange cryptographic session keys
    that cannot be intercepted without disturbing the quantum state.

    For now, this implements the classical simulation layer that mirrors the
    exact interface the QKD hardware driver would call — enabling drop-in
    replacement once hardware is available.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict], None]]] = {}
        self._lock = threading.Lock()
        self._sequence = 0

    def subscribe(self, channel: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append(callback)
        logger.debug(f"[QBus] Subscribed to channel '{channel}'")

    def publish(self, channel: str, payload: dict[str, Any]) -> None:
        """
        Publishes a message. In production QKD mode, this would:
        1. Generate a fresh one-time pad from quantum random number generator (QRNG)
        2. XOR the serialized payload with the OTP
        3. Transmit over a fibre optic channel where any interception collapses the quantum state
        """
        with self._lock:
            self._sequence += 1
            envelope = {
                "seq": self._sequence,
                "channel": channel,
                "payload": payload,
            }
            callbacks = list(self._subscribers.get(channel, []))

        for cb in callbacks:
            try:
                cb(envelope)
            except Exception as exc:
                logger.error(f"[QBus] Callback error on channel '{channel}': {exc}")

    def generate_qrng_seed(self, n_bytes: int = 32) -> bytes:
        """
        In production: calls into the QKD hardware driver (e.g., ID Quantique Cerberis).
        In simulation: uses os.urandom as a cryptographically secure fallback.
        """
        import os

        raw = os.urandom(n_bytes)
        logger.debug(f"[QBus] Generated {n_bytes}-byte QRNG seed (simulation mode)")
        return raw
