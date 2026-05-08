import logging
from typing import Dict

import requests

logger = logging.getLogger(__name__)

class ESGAlphaAgent:
    """
    Correlates ESG (Environmental, Social, Governance) scores with forward stock returns.
    Academic evidence (Friede et al., 2015: 2,200 studies) shows positive ESG-alpha
    correlation, especially in governance (G) scores and institutional ownership.
    """
    def estimate_esg_alpha(self, esg_scores: Dict[str, float]) -> Dict:
        e = esg_scores.get("environmental", 50.0)
        s = esg_scores.get("social", 50.0)
        g = esg_scores.get("governance", 50.0)
        # Governance is the strongest predictor of forward returns
        composite = (e * 0.25 + s * 0.25 + g * 0.50) / 100.0
        alpha_estimate_bps = (composite - 0.5) * 40
        signal = "OVERWEIGHT" if composite > 0.65 else "UNDERWEIGHT" if composite < 0.35 else "NEUTRAL"
        logger.info(f"[ESG] Composite={composite:.2f} | Alpha={alpha_estimate_bps:+.1f}bps | Signal={signal}")
        return {"composite": round(composite, 3), "alpha_bps": round(alpha_estimate_bps, 2), "signal": signal,
                "breakdown": {"E": e, "S": s, "G": g}}

    def governance_risk_flag(self, insider_ownership_pct: float, board_independence_pct: float) -> bool:
        risky = insider_ownership_pct > 70 or board_independence_pct < 30
        if risky: logger.warning(f"[ESG] Governance risk: insider={insider_ownership_pct:.0f}% board_ind={board_independence_pct:.0f}%")
        return risky
