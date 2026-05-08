import logging
logger = logging.getLogger(__name__)

class SelfHealer:
    def __init__(self):
        self.error_counts = {}

    def log_error(self, module_name: str):
        self.error_counts[module_name] = self.error_counts.get(module_name, 0) + 1
        if self.error_counts[module_name] > 3:
            self.attempt_heal(module_name)

    def attempt_heal(self, module_name: str):
        logger.warning(f"Attempting hot-reload to heal {module_name}")
        self.error_counts[module_name] = 0
