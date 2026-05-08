from multiprocessing import shared_memory
import logging
logger = logging.getLogger(__name__)

class ZeroCopyManager:
    """Manages zero-copy shared memory blocks between Python processes."""
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size
        self.shm = None

    def allocate(self) -> bool:
        try:
            self.shm = shared_memory.SharedMemory(create=True, size=self.size, name=self.name)
            logger.info(f"Allocated zero-copy memory block: {self.name} ({self.size} bytes)")
            return True
        except FileExistsError:
            self.shm = shared_memory.SharedMemory(name=self.name)
            return True

    def cleanup(self) -> None:
        if self.shm:
            self.shm.close()
            self.shm.unlink()
