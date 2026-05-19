import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class InvestmentThesisWriter:
    """
    Generates a structured investment thesis document for each quorum decision.
    Formats the evidence, quorum breakdown, risk factors, and expected return
    into a readable PDF-ready report for compliance and audit purposes.
    """

    def generate(self, decision: Dict[str, Any], market_context: Dict[str, Any]) -> str:
        ticker = decision.get("ticker", "UNKNOWN")
        action = decision.get("decision", "UNKNOWN")
        confidence = decision.get("confidence", 0.0)
        reason = decision.get("reason", "No rationale recorded.")
        votes = decision.get("votes", [])
        yes_agents = [v["agent"] for v in votes if v.get("vote") == "YES"]
        no_agents = [v["agent"] for v in votes if v.get("vote") == "NO"]
        vix = market_context.get("vix", 0.0)
        regime = market_context.get("regime", "UNKNOWN")
        ts = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

        thesis = f"""
====================================================
SOVEREIGN INVESTMENT THESIS
Generated: {ts}
====================================================
TICKER:     {ticker}
ACTION:     {action}
CONFIDENCE: {confidence:.1%}
REGIME:     {regime}  |  VIX: {vix:.1f}

RATIONALE
---------
{reason}

QUORUM BREAKDOWN
----------------
YES ({len(yes_agents)}): {", ".join(yes_agents) or "None"}
NO  ({len(no_agents)}): {", ".join(no_agents) or "None"}

RISK FACTORS
------------
- Conviction below 70% triggers automatic half-size execution
- VIX > 30 triggers protective put overlay
- Position exited if daily loss exceeds 1.5% NAV

====================================================
""".strip()
        logger.info(f"[THESIS] Generated for {ticker} ({action} @ {confidence:.0%})")
        return thesis
