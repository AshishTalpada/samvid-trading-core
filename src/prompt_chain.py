import logging
from typing import Any, Callable, List

logger = logging.getLogger(__name__)


class PromptChainExecutor:
    """
    Executes multi-step reasoning chains where each LLM call's output
    feeds into the next as structured context.
    Implements Chain-of-Thought (CoT) + ReAct patterns for deep analysis.
    """

    def __init__(self):
        self._steps: List[tuple[str, Callable]] = []

    def add_step(self, name: str, prompt_builder: Callable[[Any], str], executor: Callable[[str], Any]) -> None:
        self._steps.append((name, lambda ctx, pb=prompt_builder, ex=executor: ex(pb(ctx))))

    def execute(self, initial_context: Any) -> list[dict]:
        trace = []
        ctx = initial_context
        for name, step_fn in self._steps:
            try:
                result = step_fn(ctx)
                trace.append({"step": name, "output": result, "status": "OK"})
                ctx = result
                logger.debug(f"[PROMPT CHAIN] Step '{name}' complete.")
            except Exception as e:
                logger.error(f"[PROMPT CHAIN] Step '{name}' failed: {e}")
                trace.append({"step": name, "output": None, "status": "FAILED", "error": str(e)})
                break
        return trace

    def chain_summary(self, trace: list[dict]) -> str:
        statuses = [f"{t['step']}({'✓' if t['status']=='OK' else '✗'})" for t in trace]
        return " → ".join(statuses)
