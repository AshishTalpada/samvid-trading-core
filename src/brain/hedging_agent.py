import logging
from typing import Any
logger = logging.getLogger(__name__)

class HedgingAgent:
    """
    Auto-buys Puts when the SLM or tail-risk model senses a crash coming.
    """
    def __init__(self, hedge_ratio: float = 0.05):
        # Default: spend 5% of portfolio value on hedges during high risk
        self.hedge_ratio = hedge_ratio
        
    def evaluate_hedge_requirements(self, portfolio_value: float, vix_level: float, 
                                  slm_crash_probability: float, tail_risk_var: float) -> dict[str, Any]:
        """
        Determine if the portfolio needs protective puts based on market conditions.
        """
        needs_hedge = False
        reason = ""
        allocation = 0.0
        
        if vix_level > 35.0:
            needs_hedge = True
            reason = "VIX Extreme Spike"
        elif slm_crash_probability > 0.80:
            needs_hedge = True
            reason = "SLM predicts high crash probability"
        elif tail_risk_var < -0.15: # Expecting > 15% drop
            needs_hedge = True
            reason = "Severe Tail Risk detected"
            
        if needs_hedge:
            # Dynamic allocation based on crash probability
            severity_multiplier = max(1.0, slm_crash_probability * 2)
            allocation = portfolio_value * self.hedge_ratio * severity_multiplier
            logger.info(f"Hedging Agent triggered! Reason: {reason}. Suggested Allocation: ${allocation:.2f}")
            
        return {
            "needs_hedge": needs_hedge,
            "reason": reason,
            "suggested_put_allocation": allocation,
            "target_delta": -0.30 if needs_hedge else 0.0 # Target 30-delta OTM puts
        }
