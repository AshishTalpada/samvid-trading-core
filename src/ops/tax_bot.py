import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

# Tax jurisdiction rates
TAX_RATES = {
    "us_short_term": 0.37,    # Ordinary income rate for <1yr holds
    "us_long_term":  0.20,    # LTCG rate for >1yr holds
    "uk_cgt":        0.20,
    "india_stcg":    0.15,
    "india_ltcg":    0.10,
}


@dataclass
class TaxLot:
    ticker: str
    quantity: float
    cost_basis: float
    hold_days: int


@dataclass
class TaxEstimate:
    gross_pnl: float
    estimated_tax: float
    net_pnl: float
    jurisdiction: str
    rate_applied: float


class TaxBot:
    """
    After-Tax Return Calculator.
    Converts gross trading PnL into net after-tax returns.
    Applies FIFO lot matching and jurisdiction-specific tax rates.
    Prevents the AI from chasing trades with high gross returns but poor net returns.
    """

    def __init__(self, jurisdiction: str = "us") -> None:
        self.jurisdiction = jurisdiction

    def estimate_tax(self, lots: List[TaxLot], exit_price: float) -> TaxEstimate:
        """
        Calculates tax on a set of lots being sold at exit_price.
        Uses FIFO (First In, First Out) lot matching.
        """
        gross_pnl = 0.0
        total_tax = 0.0

        for lot in lots:
            lot_pnl = (exit_price - lot.cost_basis) * lot.quantity

            # Determine applicable rate
            if self.jurisdiction == "us":
                rate_key = "us_long_term" if lot.hold_days >= 365 else "us_short_term"
            elif self.jurisdiction == "uk":
                rate_key = "uk_cgt"
            elif self.jurisdiction == "india":
                rate_key = "india_ltcg" if lot.hold_days >= 365 else "india_stcg"
            else:
                rate_key = "us_short_term"

            rate = TAX_RATES[rate_key]
            tax = max(0.0, lot_pnl * rate)  # No tax credit on losses (simplified)

            gross_pnl += lot_pnl
            total_tax += tax

        net_pnl = gross_pnl - total_tax
        blended_rate = (total_tax / gross_pnl) if gross_pnl > 0 else 0.0

        logger.info(
            f"[TAX BOT] Gross: ${gross_pnl:.2f} | Tax: ${total_tax:.2f} | Net: ${net_pnl:.2f} | Rate: {blended_rate*100:.1f}%"
        )

        return TaxEstimate(
            gross_pnl=gross_pnl,
            estimated_tax=total_tax,
            net_pnl=net_pnl,
            jurisdiction=self.jurisdiction,
            rate_applied=blended_rate,
        )
