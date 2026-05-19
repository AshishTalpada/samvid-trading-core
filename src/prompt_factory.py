import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PromptFactory:
    """
    Dynamically generates agent prompts based on the current market VIX.
    During high VIX, prompts are automatically rewritten to demand higher
    certainty and explicit risk warnings.
    """

    def __init__(self):
        self.base_prompt = "Analyze the following asset and provide a BUY/SELL/HOLD recommendation."

    def build_agent_prompt(self, asset: str, current_vix: float) -> str:
        prompt = f"{self.base_prompt}\nAsset: {asset}\nCurrent VIX: {current_vix:.1f}\n\n"

        if current_vix > 30.0:
            prompt += (
                "CRITICAL: Market is in severe distress (VIX > 30). "
                "Prioritize capital preservation over returns. "
                "Reject any setup with a win probability < 80%."
            )
        elif current_vix < 15.0:
            prompt += (
                "Market regime is complacent (VIX < 15). "
                "Focus on trend continuation and momentum breakouts. "
                "Be wary of sudden mean-reversion."
            )
        else:
            prompt += "Market is in standard operating regime. Apply normal risk parameters."

        return prompt
