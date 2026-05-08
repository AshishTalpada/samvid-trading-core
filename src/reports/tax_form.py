import csv
import io
import logging
import time
from typing import Dict, List

logger = logging.getLogger(__name__)


class Form8949Generator:
    """
    Automatically generates IRS Form 8949 (Sales and Dispositions of Capital Assets).
    Produces a CSV-formatted report for direct import into tax software (TurboTax, H&R Block).
    Separates short-term and long-term lots per IRS requirements.
    """

    HEADER = ["Description", "Date Acquired", "Date Sold", "Proceeds", "Cost Basis",
              "Adjustment Code", "Adjustment Amount", "Gain or Loss"]

    def generate(self, closed_lots: List[Dict]) -> Dict[str, str]:
        short_term, long_term = [], []
        for lot in closed_lots:
            hold_days = lot.get("hold_days", 0)
            row = [
                f"{lot.get('qty', 0):.0f} SHS {lot.get('ticker', 'UNKN')}",
                lot.get("date_acquired", ""),
                lot.get("date_sold", ""),
                f"{lot.get('proceeds', 0):.2f}",
                f"{lot.get('cost_basis', 0):.2f}",
                "",
                "0.00",
                f"{lot.get('proceeds', 0) - lot.get('cost_basis', 0):.2f}",
            ]
            if hold_days < 365:
                short_term.append(row)
            else:
                long_term.append(row)

        def to_csv(rows: List) -> str:
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(self.HEADER)
            w.writerows(rows)
            return buf.getvalue()

        logger.info(f"[TAX FORM] Generated Form 8949: {len(short_term)} ST, {len(long_term)} LT lots")
        return {"short_term_csv": to_csv(short_term), "long_term_csv": to_csv(long_term)}
