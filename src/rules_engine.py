import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

class NeuroSymbolicRulesEngine:
    """
    Hard logical constraint wrapper around the AI's probabilistic outputs.
    Rules are absolute and cannot be overridden by any confidence level.
    Uses forward-chaining inference over a rule set.
    """
    def __init__(self):
        self._rules: list[tuple[str, Callable[[dict], bool], str]] = []

    def add_rule(self, name: str, condition: Callable[[dict], bool], action: str) -> None:
        self._rules.append((name, condition, action))
        logger.debug(f"[RULES] Added rule: {name}")

    @classmethod
    def default_ruleset(cls) -> "NeuroSymbolicRulesEngine":
        engine = cls()
        engine.add_rule("MaxDailyLoss",   lambda ctx: ctx.get("daily_loss_pct", 0) > 0.04, "HALT_TRADING")
        engine.add_rule("VIXCircuitBreak", lambda ctx: ctx.get("vix", 0) > 40, "GO_FLAT")
        engine.add_rule("MarginCall",     lambda ctx: ctx.get("margin_ratio", 1) < 0.15, "REDUCE_SIZE")
        engine.add_rule("ConcentrationRisk", lambda ctx: ctx.get("largest_position_pct", 0) > 0.25, "TRIM_POSITION")
        return engine

    def evaluate(self, context: dict[str, Any]) -> list[tuple[str, str]]:
        triggered = []
        for name, condition, action in self._rules:
            try:
                if condition(context):
                    logger.warning(f"[RULES] Rule triggered: {name} -> {action}")
                    triggered.append((name, action))
            except Exception as e:
                logger.error(f"[RULES] Rule '{name}' evaluation error: {e}")
        return triggered
