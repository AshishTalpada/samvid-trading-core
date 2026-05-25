import logging
import queue
import threading

logger = logging.getLogger(__name__)


class LiveAudioDubber:
    """
    Real-time audio commentary engine for Sovereign trade events.
    Uses a background worker thread and a non-blocking queue to generate
    spoken alerts via system TTS, avoiding any latency impact on the trading loop.
    """

    def __init__(self, voice_rate: int = 175, voice_volume: float = 0.9) -> None:
        self._queue: queue.Queue[str] = queue.Queue(maxsize=20)
        self._rate = voice_rate
        self._volume = voice_volume
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="AudioDubber")
        self._thread.start()
        logger.info("[AUDIO] Live dub worker started.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def announce(self, message: str) -> None:
        """Non-blocking: drops the message if the queue is full."""
        try:
            self._queue.put_nowait(message)
        except queue.Full:
            logger.debug("[AUDIO] Queue full. Dropping announcement.")

    def announce_trade(self, action: str, symbol: str, price: float) -> None:
        msg = f"Sovereign {action} {symbol} at {price:.2f}"
        self.announce(msg)

    def _worker(self) -> None:
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
        except ImportError:
            logger.warning("[AUDIO] pyttsx3 not installed. Audio disabled.")
            return

        while self._running:
            try:
                msg = self._queue.get(timeout=0.5)
                logger.info(f"[AUDIO] Speaking: {msg}")
                engine.say(msg)
                engine.runAndWait()
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error(f"[AUDIO] TTS error: {exc}")
