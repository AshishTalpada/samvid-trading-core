import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

class BiometricPrimeDirective:
    """
    Core safety protocol enforcing that fundamental system rule changes
    (e.g., maximum drawdown limit, leverage limit) require physical biometric
    verification (FaceID/TouchID via mobile link) to prevent remote hijack
    or AI-hallucinated parameter drift.
    """
    def __init__(self):
        self._biometric_verifier: Callable[[], bool] = lambda: False
        self._prime_rules = {
            "max_daily_loss_pct": 2.0,
            "max_leverage": 3.0,
            "allow_crypto": False
        }

    def register_verifier(self, verifier_fn: Callable[[], bool]) -> None:
        self._biometric_verifier = verifier_fn

    def request_rule_change(self, rule: str, new_value: Any) -> bool:
        if rule not in self._prime_rules:
            logger.error(f"[PRIME DIRECTIVE] Cannot change unknown rule: {rule}")
            return False

        logger.warning(f"[PRIME DIRECTIVE] Requesting change to {rule} -> {new_value}. Awaiting BIOMETRIC VERIFICATION.")

        if self._biometric_verifier():
            old_val = self._prime_rules[rule]
            self._prime_rules[rule] = new_value
            logger.critical(f"[PRIME DIRECTIVE] BIOMETRIC VERIFIED. {rule} changed from {old_val} to {new_value}.")
            return True

        logger.error("[PRIME DIRECTIVE] BIOMETRIC VERIFICATION FAILED. Rule change rejected.")
        return False

    def get_rule(self, rule: str) -> Any:
        return self._prime_rules.get(rule)
