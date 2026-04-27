import logging

from memdir import MemoryManager

logger = logging.getLogger(__name__)


class MindPrompts:
    """
    Context Injector for the SETO V4.0 Prime Architecture.
    Constructs meticulous system prompts for the minds.
    Inspired by Claude-Code's 'prompts.ts' and 'context.ts' logic.
    """

    def __init__(self, memory: MemoryManager) -> None:
        self.memory = memory
        self.system_identity = (
            "You are a core mind in a SETO (Self-Evolving Trading Organism) V9.0 Sovereign. "
            "You operate in a high-stakes financial environment where code integrity and risk management are paramount."
        )

    def build_architect_prompt(self) -> str:
        """Construct the prompt for Agent G (The Healer)."""
        prompt = [
            f"IDENTITY: {self.system_identity}",
            "YOUR PURPOSE: You are the 'Healer Mind'. Monitor for system 'bleeds' (errors) and perform 'Suture' edits to fix the code.",
            "",
            self.memory.get_full_context(),
            "",
            "### FINAL MANDATE:",
            "CORE RULES:",
            "- Always perform a syntax check before applying a patch.",
            "- Prioritize system stability and order execution over strategic improvements.",
            "- If a trade is losing profit, analyze the code for bugs in the execution layer.",
            "YOU ARE THE HEALER. DO NOT FAIL THE ORGANISM.",
        ]
        return "\n".join(prompt)

    def build_evolution_prompt(self, current_regime: str, win_rate: float) -> str:
        """Construct the prompt for Agent D/E (The Strategist)."""
        # GAP-72 FIX: Removed 'Gambler Instructions'.
        # Replaced 'Velocity Accelerator' with 'Risk Invariance'.
        prompt = [
            f"IDENTITY: {self.system_identity}",
            "YOUR PURPOSE: You are the 'Master Evolution Mind'. Track peak equity and optimize risk thresholds.",
            f"CURRENT REGIME: {current_regime}",
            f"CURRENT WIN RATE: {win_rate:.2%}",
            "",
            self.memory.get_full_context(),
            "",
            "### FINAL MANDATE:",
            "CORE RULES:",
            "- Strictly honor hardcoded 'RiskInvariants'; never propose parameters that exceed defined safety bounds.",
            "- During drawdowns or low-liquidity regimes, prioritize survival over recovery. Do NOT chase volume.",
            "YOU ARE THE STRATEGIST. EVOLVE THE ALPHA SAFELY.",
        ]
        return "\n".join(prompt)

    def build_observer_prompt(self, market_sentiment: str) -> str:
        """Construct the prompt for Agent H (The Observer)."""
        prompt = [
            f"IDENTITY: {self.system_identity}",
            "YOUR PURPOSE: You are the 'Observation Mind'. Scan the 'Global Information Scent' and alert others of regime shifts.",
            f"CURRENT SENTIMENT: {market_sentiment}",
            "",
            self.memory.get_full_context(),
            "",
            "### FINAL MANDATE:",
            "CORE RULES:",
            "- Filter for 'Beta' and 'Staleness' in the environment.",
            "- Provide context to the Trader and Architect before major event windows (FOMC, CPI).",
            "YOU ARE THE OBSERVER. SEE WHAT OTHERS MISS.",
        ]
        return "\n".join(prompt)
