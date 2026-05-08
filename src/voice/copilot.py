import pyttsx3
import threading
import queue
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class SovereignVoiceCopilot:
    """
    Custom AI voice co-pilot acting as an active situational awareness interface.
    Runs continuously in a background thread, speaking critical market events,
    risk limit breaches, and arbitrage opportunities directly to the user,
    bypassing the need for visual dashboard monitoring.
    """
    def __init__(self, voice_speed: int = 180):
        self.message_queue = queue.Queue()
        self.running = True
        self.voice_speed = voice_speed
        
        # System state tracking to avoid repeating the same warning
        self.last_alerts: Dict[str, float] = {}
        
        self.worker = threading.Thread(target=self._speech_loop, daemon=True)
        self.worker.start()
        logger.info("Sovereign Voice Co-Pilot online.")

    def _speech_loop(self):
        # Initialize pyttsx3 inside the thread as it relies on COM objects on Windows
        engine = pyttsx3.init()
        engine.setProperty('rate', self.voice_speed)
        
        # Attempt to set a distinct, authoritative voice (e.g., Zira or David on Windows)
        voices = engine.getProperty('voices')
        for voice in voices:
            if "Zira" in voice.name or "Hazel" in voice.name:
                engine.setProperty('voice', voice.id)
                break
                
        engine.say("Sovereign architecture initialized and monitoring execution streams.")
        engine.runAndWait()

        while self.running:
            try:
                # Block until a message is available, timeout allows checking self.running
                priority, msg_id, message = self.message_queue.get(timeout=1.0)
                
                logger.debug(f"[COPILOT SPEAKS]: {message}")
                engine.say(message)
                engine.runAndWait()
                self.message_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Voice engine failure: {e}")

    def alert(self, msg_id: str, message: str, priority: int = 1):
        """
        Submits a message to be spoken. Priority 0 is highest (cuts the line).
        """
        import time
        current_time = time.time()
        
        # Debounce: Don't repeat the exact same alert ID within 60 seconds
        if msg_id in self.last_alerts:
            if current_time - self.last_alerts[msg_id] < 60:
                return
                
        self.last_alerts[msg_id] = current_time
        
        if priority == 0:
            # Clear the queue for critical alerts (e.g., Flash Crash, Margin Call)
            with self.message_queue.mutex:
                self.message_queue.queue.clear()
                
        self.message_queue.put((priority, msg_id, message))

    def shutdown(self):
        self.running = False
        self.worker.join(timeout=2.0)
