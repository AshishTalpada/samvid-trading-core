import logging
logger = logging.getLogger(__name__)

class MultiGPUDistributor:
    """Distributes agent inference tasks across multiple GPUs using DataParallel paradigms."""
    def __init__(self, gpu_count: int = 2):
        self.gpus = [f"cuda:{i}" for i in range(gpu_count)]
        self.task_queue: list = []

    def dispatch(self, model_name: str) -> str:
        device = self.gpus[len(self.task_queue) % len(self.gpus)]
        self.task_queue.append(model_name)
        logger.debug(f"Dispatched {model_name} to {device}")
        return device
