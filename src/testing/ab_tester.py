import logging
import uuid
from typing import Any, Dict

logger = logging.getLogger(__name__)


class StrategyABTester:
    """
    Runs two concurrent algorithmic logic variants in a live environment to determine statistical superiority.
    """

    def __init__(self):
        self.active_experiments: Dict[str, Dict[str, Any]] = {}

    def start_experiment(
        self, experiment_name: str, variant_a_name: str, variant_b_name: str
    ) -> str:
        """
        Initializes a new A/B test routing table.
        """
        exp_id = str(uuid.uuid4())
        self.active_experiments[exp_id] = {
            "name": experiment_name,
            "variants": {
                "A": {"name": variant_a_name, "trades": 0, "pnl": 0.0},
                "B": {"name": variant_b_name, "trades": 0, "pnl": 0.0},
            },
        }
        logger.info(f"Started A/B Test: {experiment_name} ({exp_id})")
        return exp_id

    def route_trade(self, exp_id: str, ticker: str) -> str:
        """
        Deterministically routes a ticker to variant A or B using hash-based routing
        to ensure the same ticker always gets the same variant logic during the test.
        """
        if exp_id not in self.active_experiments:
            return "A"  # Default fallback

        # Simple consistent hashing
        hash_val = sum(ord(c) for c in ticker)
        return "A" if hash_val % 2 == 0 else "B"

    def record_trade_result(self, exp_id: str, variant: str, pnl: float) -> None:
        """
        Logs the PnL result of a completed trade for the specified variant.
        """
        if exp_id in self.active_experiments and variant in ["A", "B"]:
            self.active_experiments[exp_id]["variants"][variant]["trades"] += 1
            self.active_experiments[exp_id]["variants"][variant]["pnl"] += pnl

    def evaluate_experiment(self, exp_id: str) -> Dict[str, Any]:
        """
        Evaluates which variant is currently winning.
        """
        if exp_id not in self.active_experiments:
            return {"error": "Experiment not found"}

        exp = self.active_experiments[exp_id]
        pnl_a = exp["variants"]["A"]["pnl"]
        pnl_b = exp["variants"]["B"]["pnl"]

        winner = "A" if pnl_a > pnl_b else ("B" if pnl_b > pnl_a else "TIE")

        return {
            "experiment_name": exp["name"],
            "winner": winner,
            "pnl_diff": abs(pnl_a - pnl_b),
            "variant_A_stats": exp["variants"]["A"],
            "variant_B_stats": exp["variants"]["B"],
        }
