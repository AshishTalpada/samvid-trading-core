import logging
from typing import Any

logger = logging.getLogger(__name__)

class TintOrchestrator:
    """
    Transformer-in-Transformer (TinT) architecture.
    A master transformer that routes sub-tasks to specialised sub-agent transformers.
    Each sub-agent processes one domain: macro, microstructure, sentiment, or technicals.
    """
    DOMAINS = ["macro", "microstructure", "sentiment", "technicals"]

    def __init__(self, sub_agents: dict[str, Any] | None = None):
        self.sub_agents = sub_agents or {}

    def route(self, context: dict[str, Any]) -> dict[str, Any]:
        results = {}
        for domain in self.DOMAINS:
            agent = self.sub_agents.get(domain)
            if agent and hasattr(agent, "evaluate"):
                try:
                    results[domain] = agent.evaluate(context)
                except Exception as e:
                    logger.error(f"[TinT] Sub-agent '{domain}' failed: {e}")
                    results[domain] = {"vote": "ABSTAIN", "confidence": 0.0}
            else:
                results[domain] = {"vote": "ABSTAIN", "confidence": 0.0}
        return results

    def aggregate(self, results: dict[str, Any]) -> dict[str, Any]:
        votes = [v["vote"] for v in results.values()]
        confs = [v["confidence"] for v in results.values()]
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        dominant = max(set(votes), key=votes.count)
        return {"vote": dominant, "confidence": avg_conf, "breakdown": results}
