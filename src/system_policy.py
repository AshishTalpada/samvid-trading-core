import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

class ApexDirective:
    """Self-enforcing system laws that cannot be overridden by any agent."""
    def __init__(self, rules: Dict[str, Any] | None = None):
        self.rules = rules or {
            "max_daily_loss_pct": 0.02,
            "max_position_pct": 0.10,
            "max_drawdown_pct": 0.15,
            "require_positive_expectancy": True,
        }

    def validate(self, daily_loss_pct: float, position_pct: float, 
                 drawdown_pct: float, expectancy: float) -> tuple[bool, list[str]]:
        violations = []
        if daily_loss_pct > self.rules["max_daily_loss_pct"]:
            violations.append(f"Daily loss {daily_loss_pct:.1%} exceeds limit {self.rules['max_daily_loss_pct']:.1%}")
        if position_pct > self.rules["max_position_pct"]:
            violations.append(f"Position size {position_pct:.1%} exceeds limit")
        if drawdown_pct > self.rules["max_drawdown_pct"]:
            violations.append(f"Drawdown {drawdown_pct:.1%} exceeds limit")
        if self.rules["require_positive_expectancy"] and expectancy <= 0:
            violations.append("Negative expectancy trade blocked by Apex Directive")
        for v in violations:
            logger.critical(f"APEX DIRECTIVE VIOLATION: {v}")
        return len(violations) == 0, violations
