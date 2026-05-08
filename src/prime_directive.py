import logging

logger = logging.getLogger(__name__)

class PrimeDirective:
    """Enforces biometric consent gate for changes to core system rules."""
    def __init__(self):
        self.authorized = False

    def authenticate(self, biometric_hash: str, expected_hash: str) -> bool:
        if biometric_hash == expected_hash:
            self.authorized = True
            logger.info("Prime Directive: Biometric authentication successful.")
            return True
        logger.critical("Prime Directive: Authentication FAILED. Core rule change blocked.")
        return False

    def authorize_rule_change(self, rule_name: str) -> bool:
        if not self.authorized:
            logger.critical(f"Unauthorized attempt to change rule: {rule_name}")
            return False
        self.authorized = False
        return True
