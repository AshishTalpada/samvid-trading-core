import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class TaxOptimisedExitStrategy:
    """
    Selects which specific lot to sell based on after-tax return optimisation.
    Max loss harvesting: sell the highest-basis lot to crystallise the largest loss.
    Long-term preference: hold positions >365 days to qualify for 20% LTCG rate vs 37% STCG.
    """

    STCG_RATE = 0.37
    LTCG_RATE = 0.20

    def select_lot_to_sell(self, open_lots: List[Dict], target_qty: float, objective: str = "min_tax") -> List[Dict]:
        import time
        now = time.time()
        for lot in open_lots:
            lot["hold_days"] = (now - lot.get("opened_at", now)) / 86400
            lot["rate"] = self.LTCG_RATE if lot["hold_days"] >= 365 else self.STCG_RATE
            lot["after_tax_loss"] = (lot.get("current_price", lot["basis"]) - lot["basis"]) * (1 - lot["rate"])

        if objective == "min_tax":
            sorted_lots = sorted(open_lots, key=lambda x: x["rate"])
        elif objective == "harvest_loss":
            sorted_lots = sorted(open_lots, key=lambda x: x["after_tax_loss"])
        else:
            sorted_lots = open_lots

        selected, filled = [], 0.0
        for lot in sorted_lots:
            if filled >= target_qty:
                break
            take = min(lot.get("qty", 0), target_qty - filled)
            selected.append({**lot, "sell_qty": take})
            filled += take

        logger.info(f"[TAX STRATEGY] Selected {len(selected)} lots ({objective}) for {filled:.0f} shares")
        return selected
