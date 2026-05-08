class PromptEvolver:
    """Adapts agent prompt templates based on the current VIX regime."""
    CALM_SUFFIX = "Be concise and decisive."
    VOLATILE_SUFFIX = "Be extremely conservative. Prioritize capital preservation."

    def adapt(self, base_prompt: str, vix: float) -> str:
        if vix > 30:
            return base_prompt + " " + self.VOLATILE_SUFFIX
        return base_prompt + " " + self.CALM_SUFFIX
