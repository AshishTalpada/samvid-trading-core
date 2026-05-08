import datetime

class AutonomousThesisWriter:
    def write_thesis(self, pnl: float, top_themes: list[str]) -> str:
        date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        thesis = f"# Sovereign Weekly Thesis - {date_str}\n\n"
        thesis += f"Performance: ${pnl:.2f}\n\n"
        thesis += "## Core Themes\n"
        for theme in top_themes:
            thesis += f"- {theme}\n"
        return thesis
