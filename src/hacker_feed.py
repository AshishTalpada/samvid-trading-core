import asyncio
import logging
import time
from typing import AsyncGenerator

import requests

logger = logging.getLogger(__name__)

# Hacker/Dark-Web Intelligence Feed Monitor.
# Scrapes Hacker News (public API) and similar structured threat intelligence feeds
# to detect early signals of: exchange hacks, DeFi exploits, regulatory raids,
# and zero-day disclosures that precede market crashes.

HN_API = "https://hacker-news.firebaseio.com/v0"

THREAT_KEYWORDS = [
    "hack",
    "exploit",
    "zero-day",
    "breach",
    "stolen",
    "rug",
    "exit scam",
    "sec",
    "doj",
    "seizure",
    "bankruptcy",
    "insolvency",
    "fraud",
    "ponzi",
    "vulnerability",
    "ransomware",
    "defi exploit",
    "bridge attack",
]


def _score_threat(title: str) -> float:
    """Returns a threat score 0.0–1.0 based on keyword density in headline."""
    title_lower = title.lower()
    hits = sum(1 for kw in THREAT_KEYWORDS if kw in title_lower)
    return min(1.0, hits / 3.0)


async def stream_hn_stories(min_score: float = 0.3) -> AsyncGenerator[dict, None]:
    """
    Streams new Hacker News stories in real time (async generator).
    Yields dicts with title, url, threat_score for any story that breaches the threshold.
    Uses asyncio.to_thread for HTTP calls to stay non-blocking.
    """
    seen: set[int] = set()

    while True:
        try:
            story_ids: list[int] = await asyncio.to_thread(
                lambda: requests.get(f"{HN_API}/newstories.json", timeout=5).json()[:100]
            )

            for sid in story_ids:
                if sid in seen:
                    continue
                seen.add(sid)

                try:
                    item = await asyncio.to_thread(
                        lambda s=sid: requests.get(f"{HN_API}/item/{s}.json", timeout=3).json()
                    )
                except requests.RequestException:
                    continue

                title = item.get("title", "")
                url = item.get("url", "")
                score = _score_threat(title)

                if score >= min_score:
                    logger.warning(f"[HACKER FEED] Threat signal ({score:.2f}): {title}")
                    yield {"title": title, "url": url, "threat_score": score, "ts": time.time()}

        except Exception as exc:
            logger.error(f"[HACKER FEED] Request failure: {exc}")

        await asyncio.sleep(60)

