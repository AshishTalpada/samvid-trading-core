import pytest

from neural_governance import AgentVote, NeuralGovernanceEngine


class TestNeuralGovernanceEngine:
    def test_unanimous_approval_passes(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        votes = [
            AgentVote("agent_a", "APPROVE", confidence=0.9, weight=1.0),
            AgentVote("agent_b", "APPROVE", confidence=0.8, weight=1.0),
        ]
        decision = gov.decide("AAPL", votes)
        assert decision.approved
        assert decision.score >= 0.60
        assert decision.audit_id.startswith("gov-")

    def test_unanimous_veto_fails(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        votes = [
            AgentVote("agent_a", "VETO", confidence=0.9, weight=1.0),
            AgentVote("agent_b", "VETO", confidence=0.8, weight=1.0),
        ]
        decision = gov.decide("AAPL", votes)
        assert not decision.approved
        assert decision.score == 0.0

    def test_conflict_detected(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        votes = [
            AgentVote("agent_a", "APPROVE", confidence=0.9, weight=1.0),
            AgentVote("agent_b", "VETO", confidence=0.9, weight=1.0),
        ]
        decision = gov.decide("AAPL", votes)
        assert any("Conflict" in c for c in decision.conflicts)

    def test_insufficient_votes_fails(self):
        gov = NeuralGovernanceEngine(threshold=0.60, min_votes=3)
        votes = [AgentVote("agent_a", "APPROVE", confidence=0.9, weight=1.0)]
        decision = gov.decide("AAPL", votes)
        assert not decision.approved

    def test_no_votes_fails(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        decision = gov.decide("AAPL", [])
        assert not decision.approved
        assert decision.reasons[0] == "No agent votes available"

    def test_audit_trail_records(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        votes = [
            AgentVote("agent_a", "APPROVE", confidence=0.9, weight=1.0),
            AgentVote("agent_b", "APPROVE", confidence=0.9, weight=1.0),
        ]
        gov.decide("AAPL", votes, context={"pattern": "VCP"})
        stats = gov.audit.stats()
        assert stats["total"] == 1
        assert stats["approved"] == 1

    def test_weight_tracker_adjusts(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        for _ in range(5):
            gov.weight_tracker.record_outcome("agent_a", True, True)
        for _ in range(5):
            gov.weight_tracker.record_outcome("agent_b", True, False)
        assert gov.weight_tracker.weight("agent_a") > 1.0
        assert gov.weight_tracker.weight("agent_b") < 1.0

    def test_trade_outcome_updates_weights(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        votes = [
            AgentVote("agent_a", "APPROVE", confidence=0.9, weight=1.0),
            AgentVote("agent_b", "VETO", confidence=0.9, weight=1.0),
        ]
        decision = gov.decide("AAPL", votes)
        gov.record_trade_outcome("AAPL", decision, 100.0)
        assert len(gov.weight_tracker._outcomes["agent_a"]) == 1
        assert len(gov.weight_tracker._outcomes["agent_b"]) == 1

    def test_health(self):
        gov = NeuralGovernanceEngine(threshold=0.60)
        health = gov.health()
        assert health["threshold"] == 0.60
        assert health["min_votes"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
