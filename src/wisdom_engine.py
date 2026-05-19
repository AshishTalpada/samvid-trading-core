import logging
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class VectorizedWisdomEngine:
    """
    Recalls 10 years of post-mortem trade lessons using FAISS/Cosine Similarity.
    Before Sovereign enters a trade, it queries this engine:
    'Have we seen a setup exactly like this? Did it work?'
    """

    def __init__(self):
        self.memory_vectors: List[np.ndarray] = []
        self.lessons: List[str] = []

    def index_lesson(self, feature_vector: np.ndarray, lesson_text: str) -> None:
        norm = np.linalg.norm(feature_vector)
        if norm > 0:
            self.memory_vectors.append(feature_vector / norm)
            self.lessons.append(lesson_text)
            logger.debug(f"[WISDOM] Indexed lesson: '{lesson_text[:30]}...'")

    def recall_similar(self, query_vector: np.ndarray, top_k: int = 3) -> List[Tuple[float, str]]:
        if not self.memory_vectors:
            return []

        q_norm = np.linalg.norm(query_vector)
        if q_norm == 0:
            return []

        q = query_vector / q_norm

        similarities = [float(np.dot(q, v)) for v in self.memory_vectors]
        ranked = sorted(
            zip(similarities, self.lessons, strict=False), key=lambda x: x[0], reverse=True
        )

        recalled = ranked[:top_k]
        for sim, lesson in recalled:
            logger.info(f"[WISDOM] Recalled (sim={sim:.2f}): {lesson}")

        return recalled
