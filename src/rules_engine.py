from typing import Any, Callable, Dict


class RulesEngine:
    """Hard-coded constraint rules that override any AI decision."""
    def __init__(self):
        self.rules: Dict[str, Callable[[Any], bool]] = {}

    def register(self, name: str, rule: Callable[[Any], bool]) -> None:
        self.rules[name] = rule

    def evaluate(self, context: Any) -> tuple[bool, list[str]]:
        violations = [name for name, rule in self.rules.items() if not rule(context)]
        return len(violations) == 0, violations
