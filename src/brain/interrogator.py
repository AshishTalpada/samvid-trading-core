import logging

logger = logging.getLogger(__name__)

class NLInterrogator:
    """Logic audit: 'Sovereign, justify that quash on DIA.'"""
    def interrogate_decision(self, trade_id: str, agent_logs: dict) -> str:
        if trade_id in agent_logs:
            reason = agent_logs[trade_id]
            logger.info(f"Interrogation response: Trade {trade_id} executed because: {reason}")
            return reason
        return "Memory purged. Cannot justify."
