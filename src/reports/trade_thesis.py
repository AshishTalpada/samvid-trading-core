import datetime

class TradeThesisGenerator:
    """Generates a structured trade thesis document for every filled order."""
    def generate(self, ticker: str, direction: str, entry: float,
                 signal_sources: list[str], agent_votes: dict[str, str]) -> str:
        now = datetime.datetime.utcnow().isoformat()
        lines = [
            f"# Trade Thesis: {ticker} {direction}",
            f"Generated: {now}",
            f"Entry Price: {entry:.4f}",
            "",
            "## Signal Sources",
        ]
        for source in signal_sources:
            lines.append(f"- {source}")
        lines += ["", "## Agent Quorum"]
        for agent, vote in agent_votes.items():
            lines.append(f"- {agent}: {vote}")
        return "
".join(lines)
