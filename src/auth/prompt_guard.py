import logging
import re

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    r"ignore (all |previous )?instructions",
    r"you are now",
    r"act as (a |an )?",
    r"disregard (your |all )?",
    r"forget (everything|your training)",
    r"new persona",
    r"system prompt",
    r"<\|.*?\|>",
    r"\[INST\]",
]


class PromptGuard:
    """
    Adversarial prompt injection shield.
    Validates all external inputs (news, Telegram commands, user prompts)
    before passing them to the SLM to prevent jailbreaks that could cause
    the AI to recommend catastrophic trades.
    """

    def __init__(self):
        self._patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

    def is_safe(self, text: str) -> bool:
        for pat in self._patterns:
            if pat.search(text):
                logger.error(f"[PROMPT GUARD] Injection detected: '{pat.pattern}' in input.")
                return False
        return True

    def sanitize(self, text: str, max_length: int = 4096) -> str:
        if not self.is_safe(text):
            return "[BLOCKED: Adversarial prompt detected]"
        clean = re.sub(r"[^\x20-\x7E\n]", "", text)
        return clean[:max_length]
