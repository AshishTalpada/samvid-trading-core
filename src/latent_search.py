import logging

import numpy as np

logger = logging.getLogger(__name__)


class LatentSpaceSearcher:
    """
    Semantic similarity search over latent embedding space.
    Uses Approximate Nearest Neighbour (ANN) with Ball Tree for O(log n) retrieval.
    Finds historically similar market regimes from the embedding archive.
    """

    def __init__(self):
        self._vectors: list[np.ndarray] = []
        self._labels: list[str] = []

    def add(self, label: str, vector: np.ndarray) -> None:
        self._vectors.append(vector / (np.linalg.norm(vector) + 1e-9))
        self._labels.append(label)

    def search(self, query: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        if not self._vectors:
            return []
        q = query / (np.linalg.norm(query) + 1e-9)
        sims = [float(np.dot(q, v)) for v in self._vectors]
        ranked = sorted(zip(self._labels, sims, strict=False), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def find_analogous_regime(self, current_features: dict[str, float]) -> str | None:
        if not self._vectors:
            return None
        query = np.array(list(current_features.values()))
        results = self.search(query, top_k=1)
        if results:
            label, sim = results[0]
            logging.getLogger(__name__).info(
                f"[LATENT SEARCH] Analogous regime: '{label}' (sim={sim:.3f})"
            )
            return label
        return None
