import logging
import queue
import threading

logger = logging.getLogger(__name__)

COMMAND_MAP = {
    "risk off": {"action": "SET_RISK", "level": 0.0},
    "risk on": {"action": "SET_RISK", "level": 1.0},
    "halt trading": {"action": "HALT", "level": 0.0},
    "resume trading": {"action": "RESUME"},
    "status": {"action": "STATUS"},
    "go flat": {"action": "FLATTEN_ALL"},
}

class VoiceInterface:
    """
    Natural language voice command interface.
    Listens via microphone (speech_recognition), parses commands,
    and dispatches to the trading system's control bus.
    """
    def __init__(self):
        self._cmd_queue: queue.Queue[dict] = queue.Queue()
        self._running = False

    def parse_command(self, text: str) -> dict | None:
        text_lower = text.lower().strip()
        for phrase, action in COMMAND_MAP.items():
            if phrase in text_lower:
                logger.info(f"[VOICE] Recognized command: '{phrase}' -> {action}")
                return action
        logger.warning(f"[VOICE] Unrecognized: '{text_lower}'")
        return None

    def listen_loop(self) -> None:
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            mic = sr.Microphone()
            logger.info("[VOICE] Microphone active. Listening...")
            with mic as source:
                recognizer.adjust_for_ambient_noise(source)
                while self._running:
                    audio = recognizer.listen(source, timeout=3)
                    try:
                        text = recognizer.recognize_google(audio)
                        cmd = self.parse_command(text)
                        if cmd: self._cmd_queue.put(cmd)
                    except Exception:
                        pass
        except ImportError:
            logger.warning("[VOICE] speech_recognition not installed.")

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self.listen_loop, daemon=True).start()

    def get_command(self) -> dict | None:
        try: return self._cmd_queue.get_nowait()
        except queue.Empty: return None
