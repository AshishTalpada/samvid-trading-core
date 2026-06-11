import datetime
import logging

logger = logging.getLogger(__name__)


class AlphaReportGenerator:
    """Generates weekly autonomous evolution reports summarizing system performance."""

    def generate(
        self, week_pnl: float, trades: int, win_rate: float, sharpe: float, new_modules: list[str]
    ) -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        week_str = now.strftime("Week of %Y-%m-%d")
        lines = [
            f"# Sovereign Alpha Report — {week_str}",
            "",
            "## Performance Summary",
            f"- PnL: ${week_pnl:,.2f}",
            f"- Trades: {trades}",
            f"- Win Rate: {win_rate:.1%}",
            f"- Sharpe Ratio: {sharpe:.2f}",
            "",
            "## System Evolution",
        ]
        for module in new_modules:
            lines.append(f"- Deployed: {module}")
        logger.info(f"Alpha report generated for {week_str}")
        return "\n".join(lines)
