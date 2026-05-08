import time
from typing import Any, Dict, List


class MultiHorizonMemory:
    """Recalls trading lessons across multiple time horizons simultaneously."""
    def __init__(self):
        self.store: List[Dict[str, Any]] = []

    def add(self, lesson: str, tags: List[str]) -> None:
        self.store.append({"lesson": lesson, "tags": tags, "ts": time.time()})

    def recall(self, horizon_days: float, tags: List[str] | None = None) -> List[str]:
        cutoff = time.time() - horizon_days * 86400
        results = [e for e in self.store if e["ts"] >= cutoff]
        if tags:
            results = [e for e in results if any(t in e["tags"] for t in tags)]
        return [e["lesson"] for e in results]
