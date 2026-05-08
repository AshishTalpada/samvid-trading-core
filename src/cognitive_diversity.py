import logging

logger = logging.getLogger(__name__)

class CognitiveDiversity:
    PERSONALITIES = ["Aggressive", "Passive", "Contrarian", "Macro-Focused"]

    def assign(self, agents: list[str]) -> dict:
        assignment = {}
        for i, agent in enumerate(agents):
            assignment[agent] = self.PERSONALITIES[i % len(self.PERSONALITIES)]
            logger.debug(f"Assigned {assignment[agent]} to {agent}")
        return assignment
