import logging
import os
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)


class AutoThesisGenerator:
    """
    Generates a comprehensive, multi-page Trade Thesis Markdown document
    justifying exactly why the Sovereign Hive Mind took a trade.
    """

    def __init__(self, output_dir: str = "docs/journal/thesis"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_thesis(
        self,
        trade_id: str,
        ticker: str,
        action: str,
        size: float,
        macro_context: Dict[str, Any],
        agent_consensus: Dict[str, Any],
        risk_metrics: Dict[str, Any],
        order_book_state: Dict[str, Any],
    ) -> str:

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filepath = os.path.join(self.output_dir, f"{ticker}_{trade_id}.md")

        # Calculate conviction score
        conviction = agent_consensus.get("conviction_score", 0.0) * 100

        content = f"""# Sovereign Trade Thesis: {action} {ticker}
**Trade ID:** `{trade_id}`
**Execution Time:** {timestamp}
**Target Size:** {size} shares
**Conviction Score:** {conviction:.2f}%

---

## 1. Executive Summary
The Sovereign Hive Mind elected to execute a **{action}** position on **{ticker}** based on a confluence of macro regime alignment, highly positive agent consensus, and favorable microstructural order book imbalance.

## 2. Macro Regime Context
*The broader market environment in which this trade was taken.*
- **VIX State:** {macro_context.get("vix", "Normal")}
- **Interest Rate Trend:** {macro_context.get("rates", "Stable")}
- **Sector Rotation Momentum:** {macro_context.get("sector_momentum", "Neutral")}
- **Systematic Bias:** {macro_context.get("bias", "Neutral")}

## 3. Agent Consensus Breakdown
*How the various neural agents voted on this opportunity.*
"""
        for agent, logic in agent_consensus.get("votes", {}).items():
            content += f"- **{agent}**: {logic}\n"

        content += f"""
## 4. Quantitative Risk Parameters
*Mathematical boundaries securing the position.*
- **Entry Price:** ${risk_metrics.get("entry_price", 0.0):.2f}
- **Hard Stop Loss:** ${risk_metrics.get("stop_loss", 0.0):.2f}
- **Take Profit Target:** ${risk_metrics.get("take_profit", 0.0):.2f}
- **Risk-to-Reward Ratio:** {risk_metrics.get("rr_ratio", 0.0):.2f}
- **Kelly Criterion Size Allocation:** {risk_metrics.get("kelly_pct", 0.0) * 100:.2f}% of portfolio
- **Value at Risk (VaR 99%):** ${risk_metrics.get("var_99", 0.0):.2f}

## 5. Microstructure & Order Book Topology
*The millisecond-level state of the Limit Order Book during execution.*
- **Top of Book Spread:** {order_book_state.get("spread_bps", 0.0):.2f} bps
- **Volume Imbalance (Top 5 Levels):** {order_book_state.get("imbalance", 0.0) * 100:.2f}% (Positive = Bid heavy)
- **Detected Icebergs:** {order_book_state.get("icebergs_detected", "None")}

---
*Generated autonomously by Sovereign AutoThesis Engine.*
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Thesis successfully generated at {filepath}")
        return filepath
