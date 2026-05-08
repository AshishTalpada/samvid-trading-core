from typing import List, Dict
import logging
logger = logging.getLogger(__name__)

class WisdomEngine:
    """Indexes post-mortems and historical lessons for millisecond similarity retrieval."""
    def __init__(self):
        self.entries: List[Dict] = []

    def add(self, text: str, tags: List[str], outcome: str) -> None:
        self.entries.append({"text": text, "tags": set(tags), "outcome": outcome})

    def retrieve(self, query_tags: List[str], top_k: int = 5) -> List[Dict]:
        scored = []
        query_set = set(query_tags)
        for entry in self.entries:
            score = len(entry["tags"] & query_set) / max(len(entry["tags"] | query_set), 1)
            scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:top_k]]
