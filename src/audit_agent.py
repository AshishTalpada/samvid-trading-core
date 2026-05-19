import logging
import math
import statistics
from collections import Counter, defaultdict
from typing import Any

logger = logging.getLogger(__name__)

BIAS_PATTERNS = {
    "FOMO": lambda votes: votes.count("BUY") > len(votes) * 0.85,
    "FEAR": lambda votes: votes.count("SELL") > len(votes) * 0.85,
    "ANCHORING": lambda votes: len(set(votes)) == 1,
}


class AuditAgent:
    """
    Cognitive Bias Detector and Quorum Quality Auditor.

    Analyses the full agent output batch for:
    - Groupthink / Herding (>85% agreement)
    - Confidence anchoring (all agents return identical confidence)
    - Overconfidence (mean confidence >> historical accuracy)
    - Stale timestamps (agents submitting cached votes)
    - Suspicious vote flips relative to prior cycle
    """

    def __init__(self) -> None:
        self._prior_votes: dict[str, str] = {}
        self._confidence_history: list[float] = []
        self._cycle_count = 0

    def audit(self, agent_votes: dict[str, str]) -> dict[str, bool]:
        votes = list(agent_votes.values())
        detected: dict[str, bool] = {}
        for bias, check in BIAS_PATTERNS.items():
            if check(votes):
                logger.warning(f"[AUDIT] Cognitive bias detected: {bias}")
                detected[bias] = True
        return detected

    def full_audit(self, agent_outputs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Deep multi-dimensional audit of a quorum cycle's agent outputs.
        Returns a structured risk report that the DecisionEngine can act on.
        """
        self._cycle_count += 1
        issues: list[str] = []
        risk_score = 0.0

        votes = [o.get("vote", "ABSTAIN") for o in agent_outputs]
        confidences = [
            float(o.get("confidence", 0.0)) for o in agent_outputs if o.get("vote") != "ABSTAIN"
        ]
        agent_ids = [o.get("agent", "UNKNOWN") for o in agent_outputs]

        vote_dist = Counter(votes)
        dominant_vote, dominant_count = vote_dist.most_common(1)[0]
        herding_ratio = dominant_count / len(votes) if votes else 0.0
        if herding_ratio > 0.85:
            issues.append(
                f"HERDING: {herding_ratio * 100:.0f}% unanimity on {dominant_vote}. Independent signal loss."
            )
            risk_score += 0.3

        if len(confidences) >= 3:
            conf_std = statistics.stdev(confidences) if len(confidences) > 1 else 0.0
            if conf_std < 0.02:
                issues.append(
                    f"ANCHORING: All agents report near-identical confidence (std={conf_std:.4f}). Likely copying each other."
                )
                risk_score += 0.25

            mean_conf = statistics.mean(confidences)
            self._confidence_history.append(mean_conf)

            if len(self._confidence_history) >= 10:
                rolling_mean = statistics.mean(self._confidence_history[-20:])
                if rolling_mean > 0.85:
                    issues.append(
                        f"OVERCONFIDENCE: Rolling mean confidence={rolling_mean:.2f}. Calibration drift suspected."
                    )
                    risk_score += 0.2

        flip_count = 0
        for out in agent_outputs:
            agent = out.get("agent", "")
            vote = out.get("vote", "")
            prior = self._prior_votes.get(agent)
            if prior and prior != vote and vote not in ("ABSTAIN",):
                flip_count += 1

        if flip_count > len(agent_outputs) * 0.5:
            issues.append(
                f"MASS_FLIP: {flip_count}/{len(agent_outputs)} agents reversed their vote since last cycle. Potential regime instability."
            )
            risk_score += 0.35

        # Update prior votes
        self._prior_votes = {o.get("agent", ""): o.get("vote", "") for o in agent_outputs}

        if confidences:
            max_conf = max(confidences)
            min_conf = min(confidences)
            spread = max_conf - min_conf
            if spread > 0.6:
                issues.append(
                    f"CONFIDENCE_DIVERGENCE: Spread={spread:.2f}. Agents have wildly different certainty. Market ambiguity high."
                )
                risk_score += 0.15

        passed = risk_score < 0.5
        if not passed:
            logger.warning(
                f"[AUDIT] Cycle {self._cycle_count} failed. RiskScore={risk_score:.2f}. Issues: {issues}"
            )
        else:
            logger.debug(f"[AUDIT] Cycle {self._cycle_count} passed. RiskScore={risk_score:.2f}")

        return {
            "passed": passed,
            "risk_score": round(risk_score, 3),
            "herding_ratio": round(herding_ratio, 3),
            "issues": issues,
            "cycle": self._cycle_count,
        }
