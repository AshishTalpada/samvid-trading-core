import logging

logger = logging.getLogger(__name__)

class AutoThesis:
    """Audit edge: System writes a multi-page markdown thesis for every trade."""
    def generate_thesis(self, ticker: str, agent_logs: dict, metrics: dict) -> str:
        thesis = f"# Sovereign Trade Thesis: {ticker}\n\n"
        thesis += "## 1. Macro Convergence\n"
        thesis += f"The global macro environment aligns with a {metrics.get('direction', 'LONG')} bias.\n\n"

        thesis += "## 2. Agent Consensus\n"
        for agent, logic in agent_logs.items():
            thesis += f"- **{agent}**: {logic}\n"

        thesis += "\n## 3. Risk Parameters\n"
        thesis += f"Sizing: {metrics.get('size', 0)} shares. Stop Loss: {metrics.get('stop', 0)}.\n"

        # Save to disk
        filepath = f"docs/journal/thesis_{ticker}.md"
        with open(filepath, 'w') as f:
            f.write(thesis)

        logger.info(f"Thesis generated: {filepath}")
        return filepath
