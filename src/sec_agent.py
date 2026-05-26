import asyncio
import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class SECSemanticAgent:
    """
    SEC EDGAR full-text semantic search agent.
    Searches 20+ years of filings for specific risk phrases
    (e.g., 'going concern', 'material weakness', 'regulatory investigation')
    before they manifest as price crashes.
    """

    EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST/search-index?q={}&category=form-type&dateRange=custom&startdt={}&enddt={}"
    RED_FLAG_PHRASES = [
        "going concern",
        "material weakness",
        "regulatory investigation",
        "substantial doubt",
        "liquidity risk",
        "criminal investigation",
    ]

    async def search(
        self, query: str, start_date: str = "2020-01-01", end_date: str = "2025-12-31"
    ) -> List[Dict]:
        def _blocking_search():
            url = self.EDGAR_FULL_TEXT.format(requests.utils.quote(query), start_date, end_date)
            r = requests.get(url, timeout=8)
            hits = r.json().get("hits", {}).get("hits", [])
            return [
                {
                    "entity": h.get("_source", {}).get("entity_name", ""),
                    "date": h.get("_source", {}).get("file_date", ""),
                }
                for h in hits[:10]
            ]

        try:
            return await asyncio.to_thread(_blocking_search)
        except Exception as e:
            logger.error(f"[SEC] Search failed: {e}")
            return []

    async def red_flag_scan(self, ticker: str) -> Dict[str, int]:
        tasks = []
        for phrase in self.RED_FLAG_PHRASES:
            tasks.append(self.search(f'"{ticker}" "{phrase}"'))

        search_results = await asyncio.gather(*tasks)

        results = {}
        for phrase, hits in zip(self.RED_FLAG_PHRASES, search_results, strict=True):
            results[phrase] = len(hits)
            if hits:
                logger.warning(f"[SEC] Red flag '{phrase}' for {ticker}: {len(hits)} filings")
        return results
