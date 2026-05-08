import logging
logger = logging.getLogger(__name__)

class LiveTrainer:
    """Applies gradient updates to agent parameters after every successful live trade."""
    def __init__(self, lr: float = 1e-6, batch_size: int = 32):
        self.lr = lr
        self.batch_size = batch_size
        self.buffer: list[dict] = []

    def add_experience(self, state: list[float], action: str, reward: float) -> None:
        self.buffer.append({"state": state, "action": action, "reward": reward})

    def should_update(self) -> bool:
        return len(self.buffer) >= self.batch_size

    def flush(self) -> list[dict]:
        batch = self.buffer[-self.batch_size:]
        self.buffer = []
        logger.debug(f"Live trainer flushing batch of {len(batch)} experiences.")
        return batch
