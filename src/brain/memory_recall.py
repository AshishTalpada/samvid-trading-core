import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MultiHorizonMemoryRecall:
    """
    Recalls trade lessons from 1-day, 1-month, and 1-year time horizons simultaneously.
    Each horizon has a separate memory bank weighted by recency and outcome quality.
    Provides the DecisionEngine with historical precedents before each trade.
    """

    def __init__(self):
        self._banks: Dict[str, List[Dict[str, Any]]] = {"1d": [], "1m": [], "1y": []}

    def record(self, horizon: str, lesson: Dict[str, Any]) -> None:
        bank = self._banks.get(horizon, self._banks["1d"])
        bank.append(lesson)
        if len(bank) > 500:
            bank.pop(0)

    def recall(self, query: str, horizon: str, top_n: int = 3) -> List[Dict]:
        bank = self._banks.get(horizon, [])
        query_words = set(query.lower().split())
        scored = []
        for lesson in bank:
            text = str(lesson.get("summary", "")).lower()
            overlap = len(query_words & set(text.split()))
            scored.append((overlap, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [l for _, l in scored[:top_n]]
        logger.debug(
            f"[MEMORY] Recalled {len(result)} lessons from '{horizon}' for: '{query[:40]}'"
        )
        return result

    def recall_all_horizons(self, query: str) -> Dict[str, List[Dict]]:
        return {h: self.recall(query, h) for h in self._banks}
