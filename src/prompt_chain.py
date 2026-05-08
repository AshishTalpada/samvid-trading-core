import logging

logger = logging.getLogger(__name__)

class PromptChainer:
    def __init__(self, steps: list[str] = None):
        self.steps = steps or ["Identify", "Vet", "Size", "Risk", "Execute"]

    def run_chain(self, initial_context: dict, evaluator) -> dict:
        context = dict(initial_context)
        for step in self.steps:
            logger.debug(f"Running chain step: {step}")
            context[step] = evaluator(step, context)
        return context
