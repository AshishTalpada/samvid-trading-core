import logging

logger = logging.getLogger(__name__)

VIX_THRESHOLDS = {"low": 15.0, "high": 25.0, "extreme": 35.0}

class PromptFactory:
    """
    Self-Referential Prompt Generator.
    Writes dynamic agent system prompts based on current market regime and VIX level.
    """
    def build_agent_prompt(self, agent_id: str, vix: float, regime: str, context: dict) -> str:
        tone = "aggressive and opportunistic" if vix < VIX_THRESHOLDS["low"] else \
               "cautious and defensive" if vix > VIX_THRESHOLDS["high"] else "balanced"

        prompt = f"""You are {agent_id}, a sub-agent of the Sovereign Trading System.
Current VIX: {vix:.1f} | Regime: {regime} | Operational tone: {tone}.
Your role: evaluate the following market context and return a JSON vote with keys:
  "vote" (BUY/SELL/HOLD/ABSTAIN), "confidence" (0.0-1.0), "reasoning" (one sentence).
Be {tone}. If confidence < 0.55, vote ABSTAIN. Do not hallucinate data.
Market context: {context}"""
        logger.debug(f"[PROMPT FACTORY] Built prompt for {agent_id} at VIX={vix:.1f}")
        return prompt
