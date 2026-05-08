class PromptGuard:
    """Filter malicious prompts from external sources."""
    def is_safe(self, prompt: str) -> bool:
        if "ignore all previous" in prompt.lower():
            return False
        return True
