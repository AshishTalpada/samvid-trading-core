import logging
import re
import time
from typing import Generator

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


def stream_hn_stories(min_score: float = 0.3) -> Generator[dict, None, None]:
    """
    Streams new Hacker News stories in real time.
    Yields dicts with title, url, threat_score for any story that breaches the threshold.
    """
    seen: set[int] = set()

    while True:
        try:
            resp = requests.get(f"{HN_API}/newstories.json", timeout=5)
            resp.raise_for_status()
            story_ids: list[int] = resp.json()[:100]

            for sid in story_ids:
                if sid in seen:
                    continue
                seen.add(sid)

                item_resp = requests.get(f"{HN_API}/item/{sid}.json", timeout=3)
                if item_resp.status_code != 200:
                    continue

                item = item_resp.json()
                title = item.get("title", "")
                url = item.get("url", "")
                score = _score_threat(title)

                if score >= min_score:
                    logger.warning(f"[HACKER FEED] Threat signal ({score:.2f}): {title}")
                    yield {"title": title, "url": url, "threat_score": score, "ts": time.time()}

        except requests.RequestException as exc:
            logger.error(f"[HACKER FEED] Request failure: {exc}")

        time.sleep(60)
