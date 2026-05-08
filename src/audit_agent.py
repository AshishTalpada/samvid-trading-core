import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CognitiveBiasAudit:
    """
    Cognitive Bias Audit Agent (#57 from SOVEREIGN_ULTIMATE_CHECKLIST).
    Audits agent votes for 'FOMO' or 'Fear' patterns to prevent groupthink.
    """

    FOMO_INDICATORS = [
        "fomo",
        "missing out",
        "last chance",
        "before it moon",
        "can't miss",
        "urgency",
        "all in",
        "max bet",
        "no brainer",
        "guaranteed",
    ]

    FEAR_INDICATORS = [
        "panic",
        "crash",
        "sell everything",
        "worst",
        "danger",
        "terrible",
        "collapse",
        "doom",
        "scary",
        "terrified",
        "risk off",
        "hide",
        "run",
    ]

    CONSECUTIVE_VETO_THRESHOLD = 3
    HIGH_CONFIDENCE_THRESHOLD = 0.80

    def __init__(self):
        self.veto_history = []
        self.fomo_count = 0
        self.fear_count = 0
        self.audit_log = []

    def audit_vote(self, agent_name: str, vote_text: str, confidence: float) -> dict[str, Any]:
        """
        Audit a single agent vote for cognitive bias patterns.
        
        Args:
            agent_name: Name of the voting agent
            vote_text: The voting rationale text
            confidence: Confidence level (0-1)
            
        Returns:
            Audit result with bias detection and recommendation
        """
        vote_lower = vote_text.lower()

        fomo_detected = any(indicator in vote_lower for indicator in self.FOMO_INDICATORS)
        fear_detected = any(indicator in vote_lower for indicator in self.FEAR_INDICATORS)

        result = {
            "agent": agent_name,
            "fomo_detected": fomo_detected,
            "fear_detected": fear_detected,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "recommendation": "APPROVE",
            "reason": "No bias detected",
        }

        if fomo_detected:
            self.fomo_count += 1
            result["recommendation"] = "VETO" if confidence < self.HIGH_CONFIDENCE_THRESHOLD else "WARN"
            result["reason"] = f"FOMO pattern detected in {agent_name} vote"
            result["bias_type"] = "FOMO"

        if fear_detected:
            self.fear_count += 1
            result["recommendation"] = "VETO" if confidence < self.HIGH_CONFIDENCE_THRESHOLD else "WARN"
            result["reason"] = f"Fear pattern detected in {agent_name} vote"
            result["bias_type"] = "FEAR"

        self.audit_log.append(result)
        return result

    def audit_quorum(self, votes: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Audit a complete quorum of agent votes for collective bias.
        
        Args:
            votes: List of vote dicts from agents
            
        Returns:
            Overall quorum audit with bias summary
        """
        audit_results = []
        fomo_votes = 0
        fear_votes = 0

        for vote in votes:
            agent = vote.get("agent", "unknown")
            text = vote.get("rationale", vote.get("vote_text", ""))
            confidence = vote.get("confidence", 0.5)

            result = self.audit_vote(agent, str(text), confidence)
            audit_results.append(result)

            if result["fomo_detected"]:
                fomo_votes += 1
            if result["fear_detected"]:
                fear_votes += 1

        total_votes = len(votes) if votes else 1
        fomo_ratio = fomo_votes / total_votes
        fear_ratio = fear_votes / total_votes

        collective_bias = None
        if fomo_ratio > 0.6:
            collective_bias = "COLLECTIVE_FOMO"
        elif fear_ratio > 0.6:
            collective_bias = "COLLECTIVE_FEAR"

        return {
            "bias_detected": collective_bias is not None,
            "bias_type": collective_bias,
            "fomo_count": fomo_votes,
            "fear_count": fear_votes,
            "fomo_ratio": fomo_ratio,
            "fear_ratio": fear_ratio,
            "individual_audits": audit_results,
            "recommendation": "PAUSE" if collective_bias else "PROCEED",
            "reason": f"Collective {collective_bias} detected - requires human review" if collective_bias else "No collective bias detected",
        }

    def check_consecutive_veto_pattern(self) -> dict[str, Any]:
        """
        Check for consecutive veto patterns that might indicate fear-based groupthink.
        """
        recent_vetos = self.veto_history[-self.CONSECUTIVE_VETO_THRESHOLD:]

        if len(recent_vetos) >= self.CONSECUTIVE_VETO_THRESHOLD:
            return {
                "pattern_detected": True,
                "type": "CONSECUTIVE_VETO",
                "count": len(recent_vetos),
                "recommendation": "FORCE_DEBATE",
                "reason": f"Last {len(recent_vetos)} votes were vetoed - ensure rational discussion",
            }

        return {"pattern_detected": False}

    def get_bias_summary(self) -> dict[str, Any]:
        """
        Get a summary of detected biases since initialization.
        """
        return {
            "total_fomo_detected": self.fomo_count,
            "total_fear_detected": self.fear_count,
            "total_audits": len(self.audit_log),
            "fomo_ratio": self.fomo_count / len(self.audit_log) if self.audit_log else 0,
            "fear_ratio": self.fear_count / len(self.audit_log) if self.audit_log else 0,
        }

    def reset(self):
        """Reset the audit counters."""
        self.fomo_count = 0
        self.fear_count = 0
        self.audit_log = []
        self.veto_history = []


_bias_audit_instance: CognitiveBiasAudit | None = None


def get_bias_audit() -> CognitiveBiasAudit:
    """Get the singleton CognitiveBiasAudit instance."""
    global _bias_audit_instance
    if _bias_audit_instance is None:
        _bias_audit_instance = CognitiveBiasAudit()
    return _bias_audit_instance
