"""Sovereign Neural Governance / Cross-Agent Consensus Engine.

Implementation 5 ties together all previous implementations under a single
meta-decision layer. It collects votes from every agent, resolves conflicts,
records an auditable trail for every decision, and can self-heal agent weights
based on recent accuracy.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentVote:
    """A vote from one subsystem/agent."""

    agent: str
    decision: str  # "APPROVE", "VETO", "ABSTAIN"
    confidence: float = 0.5
    reason: str = ""
    weight: float = 1.0


@dataclass
class ConsensusDecision:
    """Final decision produced by the governance engine."""

    approved: bool
    score: float  # 0.0 to 1.0
    threshold: float
    votes: list[AgentVote]
    conflicts: list[str]
    reasons: list[str]
    audit_id: str


class SovereignAuditTrail:
    """Immutable-style record of governance decisions for explainability."""

    def __init__(self, max_records: int = 1000) -> None:
        self._records: deque[dict] = deque(maxlen=max_records)

    def record(
        self,
        symbol: str,
        decision: ConsensusDecision,
        context: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "timestamp": time.monotonic(),
            "symbol": symbol,
            "approved": decision.approved,
            "score": decision.score,
            "threshold": decision.threshold,
            "votes": [
                {
                    "agent": v.agent,
                    "decision": v.decision,
                    "confidence": v.confidence,
                    "reason": v.reason,
                    "weight": v.weight,
                }
                for v in decision.votes
            ],
            "conflicts": decision.conflicts,
            "reasons": decision.reasons,
            "audit_id": decision.audit_id,
            "context": context or {},
        }
        self._records.append(entry)

    def recent(self, n: int = 10) -> list[dict]:
        return list(self._records)[-n:]

    def stats(self) -> dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"total": 0, "approved": 0, "vetoed": 0, "approval_rate": 0.0}
        approved = sum(1 for r in self._records if r["approved"])
        return {
            "total": total,
            "approved": approved,
            "vetoed": total - approved,
            "approval_rate": approved / total,
        }


class AgentWeightTracker:
    """Track agent prediction accuracy and adjust weights accordingly."""

    def __init__(self, lookback: int = 50) -> None:
        self.lookback = lookback
        self._outcomes: dict[str, deque[tuple[bool, bool]]] = {}
        self._weights: dict[str, float] = {}

    def record_outcome(self, agent: str, approved: bool, was_correct: bool) -> None:
        if agent not in self._outcomes:
            self._outcomes[agent] = deque(maxlen=self.lookback)
        self._outcomes[agent].append((approved, was_correct))

    def weight(self, agent: str, base: float = 1.0) -> float:
        if agent not in self._outcomes or len(self._outcomes[agent]) < 5:
            return base
        correct = sum(1 for _, ok in self._outcomes[agent] if ok)
        accuracy = correct / len(self._outcomes[agent])
        if accuracy >= 0.65:
            return base * 1.2
        if accuracy >= 0.45:
            return base
        return base * 0.8


class NeuralGovernanceEngine:
    """Cross-agent consensus and meta-decision engine."""

    def __init__(
        self,
        threshold: float = 0.60,
        min_votes: int = 2,
        lookback: int = 50,
    ) -> None:
        self.threshold = threshold
        self.min_votes = min_votes
        self.audit = SovereignAuditTrail()
        self.weight_tracker = AgentWeightTracker(lookback=lookback)
        self._counter = 0
        self._last_recompute = 0.0
        self._recompute_interval = 60.0

    def _next_audit_id(self) -> str:
        self._counter += 1
        return f"gov-{self._counter:06d}-{time.monotonic():.4f}"

    def decide(
        self,
        symbol: str,
        votes: list[AgentVote],
        context: dict[str, Any] | None = None,
    ) -> ConsensusDecision:
        """Produce a final consensus decision from agent votes."""
        if not votes:
            decision = ConsensusDecision(
                approved=False,
                score=0.0,
                threshold=self.threshold,
                votes=[],
                conflicts=["No votes submitted"],
                reasons=["No agent votes available"],
                audit_id=self._next_audit_id(),
            )
            self.audit.record(symbol, decision, context)
            return decision

        # Apply learned weights.
        for v in votes:
            v.weight = self.weight_tracker.weight(v.agent, v.weight)

        active_votes = [v for v in votes if v.decision != "ABSTAIN"]
        if len(active_votes) < self.min_votes:
            decision = ConsensusDecision(
                approved=False,
                score=0.0,
                threshold=self.threshold,
                votes=votes,
                conflicts=[],
                reasons=[f"Only {len(active_votes)} active vote(s); need {self.min_votes}"],
                audit_id=self._next_audit_id(),
            )
            self.audit.record(symbol, decision, context)
            return decision

        total_weight = sum(v.weight for v in active_votes)
        if total_weight == 0:
            decision = ConsensusDecision(
                approved=False,
                score=0.0,
                threshold=self.threshold,
                votes=votes,
                conflicts=[],
                reasons=["Total vote weight is zero"],
                audit_id=self._next_audit_id(),
            )
            self.audit.record(symbol, decision, context)
            return decision

        approve_weight = sum(
            v.weight * v.confidence for v in active_votes if v.decision == "APPROVE"
        )
        veto_weight = sum(
            v.weight * v.confidence for v in active_votes if v.decision == "VETO"
        )

        score = approve_weight / (approve_weight + veto_weight) if (approve_weight + veto_weight) > 0 else 0.0
        approved = score >= self.threshold and len(active_votes) >= self.min_votes

        conflicts: list[str] = []
        approve_agents = [v.agent for v in active_votes if v.decision == "APPROVE"]
        veto_agents = [v.agent for v in active_votes if v.decision == "VETO"]
        if approve_agents and veto_agents:
            conflicts.append(
                f"Conflict: {', '.join(approve_agents)} approve vs {', '.join(veto_agents)} veto"
            )

        reasons: list[str] = []
        if approved:
            reasons.append(f"Consensus score {score:.2f} >= threshold {self.threshold}")
        else:
            reasons.append(f"Consensus score {score:.2f} < threshold {self.threshold}")
        if conflicts:
            reasons.extend(conflicts)

        decision = ConsensusDecision(
            approved=approved,
            score=round(score, 3),
            threshold=self.threshold,
            votes=votes,
            conflicts=conflicts,
            reasons=reasons,
            audit_id=self._next_audit_id(),
        )
        self.audit.record(symbol, decision, context)
        return decision

    def record_trade_outcome(
        self,
        symbol: str,
        decision: ConsensusDecision,
        pnl: float,
    ) -> None:
        """Update agent weights based on whether the final decision was correct."""
        was_correct = pnl > 0
        for vote in decision.votes:
            if vote.decision == "ABSTAIN":
                continue
            # Agent was correct if its decision matched the outcome.
            agent_correct = (vote.decision == "APPROVE" and was_correct) or (
                vote.decision == "VETO" and not was_correct
            )
            self.weight_tracker.record_outcome(vote.agent, decision.approved, agent_correct)
        logger.debug(
            "Governance recorded outcome for %s: pnl=%.2f, correct=%s",
            symbol,
            pnl,
            was_correct,
        )

    async def run_async(self, bus: Any | None = None) -> None:
        """Subscribe to trade.exit events to learn from outcomes."""
        if bus is None:
            return
        try:
            bus.on("trade.exit", self._on_trade_exit)
            logger.info("NeuralGovernanceEngine subscribed to trade.exit")
        except Exception as exc:
            logger.warning("NeuralGovernanceEngine failed to subscribe to trade.exit: %s", exc)

    async def _on_trade_exit(self, payload: dict[str, Any]) -> None:
        symbol = payload.get("symbol", "")
        pnl = float(payload.get("pnl", 0.0))
        audit_id = payload.get("audit_id")
        if not audit_id:
            return
        # Find the matching audit record.
        for record in reversed(self.audit.recent(len(self.audit._records))):
            if record["audit_id"] == audit_id and record["symbol"] == symbol.upper():
                votes = [
                    AgentVote(
                        agent=v["agent"],
                        decision=v["decision"],
                        confidence=v["confidence"],
                        reason=v["reason"],
                        weight=v["weight"],
                    )
                    for v in record["votes"]
                ]
                decision = ConsensusDecision(
                    approved=record["approved"],
                    score=record["score"],
                    threshold=record["threshold"],
                    votes=votes,
                    conflicts=record["conflicts"],
                    reasons=record["reasons"],
                    audit_id=audit_id,
                )
                self.record_trade_outcome(symbol, decision, pnl)
                break

    def health(self) -> dict[str, Any]:
        """Return governance health metrics."""
        return {
            "threshold": self.threshold,
            "min_votes": self.min_votes,
            "audit_stats": self.audit.stats(),
            "agent_weights": {
                agent: self.weight_tracker.weight(agent)
                for agent in self.weight_tracker._outcomes
            },
        }


__all__ = [
    "AgentVote",
    "ConsensusDecision",
    "SovereignAuditTrail",
    "AgentWeightTracker",
    "NeuralGovernanceEngine",
]
