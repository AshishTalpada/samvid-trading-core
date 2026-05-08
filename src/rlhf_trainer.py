import logging
logger = logging.getLogger(__name__)

class RLHFTrainer:
    def __init__(self):
        self.feedback_buffer = []

    def record_override(self, ai_signal: str, human_signal: str, context: dict):
        if ai_signal != human_signal:
            self.feedback_buffer.append({'context': context, 'rejected': ai_signal, 'chosen': human_signal})
            logger.info(f"RLHF: Recorded override {ai_signal} -> {human_signal}")

    def get_training_batch(self) -> list:
        batch = self.feedback_buffer.copy()
        self.feedback_buffer.clear()
        return batch
