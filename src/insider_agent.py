import logging
import re
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class InsiderTradeAgent:
    """
    SEC Form 4 parser for real-time insider buying/selling signals.
    Clusters of insider BUYING (especially at CEOs + CFOs simultaneously) are among
    the highest-precision signals in quant finance (Seyhun 1988, Lakonishok 1995).
    """

    SEC_FEED = "https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt={}&enddt={}&hits.hits._source=period_of_report,display_names,entity_name,file_date"

    def parse_form4(self, filing: Dict) -> Dict | None:
        names = filing.get("display_names", "")
        if not any(r in names.upper() for r in ["CEO", "CFO", "DIRECTOR", "OFFICER"]):
            return None
        return {
            "ticker": filing.get("entity_name", "UNKNOWN"),
            "filer": names,
            "date": filing.get("file_date", ""),
            "type": "INSIDER",
        }

    def net_insider_sentiment(self, transactions: List[Dict]) -> float:
        """Returns +1.0 (all buying) to -1.0 (all selling)."""
        buys = sum(1 for t in transactions if t.get("transaction_type", "").upper() in ("P", "A"))
        sells = sum(1 for t in transactions if t.get("transaction_type", "").upper() in ("S", "D"))
        total = buys + sells
        return (buys - sells) / total if total > 0 else 0.0
