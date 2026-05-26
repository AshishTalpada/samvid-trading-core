import asyncio
import logging
from typing import Dict

import requests

logger = logging.getLogger(__name__)


class PatentVelocityAgent:
    """
    Tracks patent filing velocity per company as an innovation leading indicator.
    Companies filing 3x+ YoY often precede product cycle breakouts by 12-18 months.
    Sources: USPTO PatentsView API (public, no auth required).
    """

    PATENTSVIEW_API = "https://api.patentsview.org/patents/query"

    async def get_patent_count(self, assignee: str, year: int) -> int:
        try:
            payload = {
                "q": {
                    "_and": [
                        {"_contains": {"assignee_organization": assignee}},
                        {"_gte": {"patent_date": f"{year}-01-01"}},
                        {"_lte": {"patent_date": f"{year}-12-31"}},
                    ]
                },
                "f": ["patent_number"],
                "o": {"per_page": 500},
            }
            r = await asyncio.to_thread(
                requests.post, self.PATENTSVIEW_API, json=payload, timeout=8
            )
            return r.json().get("total_patent_count", 0)  # type: ignore
        except Exception as e:
            logger.error(f"[PATENT] API error for {assignee}: {e}")
            return 0

    async def velocity_score(self, assignee: str, current_year: int) -> Dict:
        curr = await self.get_patent_count(assignee, current_year)
        prev = (await self.get_patent_count(assignee, current_year - 1)) or 1
        velocity = (curr - prev) / prev
        signal = "BREAKOUT" if velocity > 2.0 else "ACCELERATING" if velocity > 0.5 else "STABLE"
        logger.info(f"[PATENT] {assignee}: {prev} -> {curr} YoY ({velocity:+.1%}) -> {signal}")
        return {
            "assignee": assignee,
            "current": curr,
            "prior": prev,
            "velocity": round(velocity, 3),
            "signal": signal,
        }
