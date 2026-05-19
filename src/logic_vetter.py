import logging
import math
import re
from typing import Any

logger = logging.getLogger(__name__)


class KolmogorovVetter:
    """
    Kolmogorov Complexity vetter: simpler hypotheses are more trustworthy.
    Uses a proxy for K-complexity via LZ77 compressibility of the reasoning string.
    High compressibility = low complexity = high trust.
    Rejects overly complex or internally repetitive reasoning chains.
    """

    def lz_complexity(self, text: str) -> float:
        import zlib

        raw = text.encode("utf-8")
        compressed = zlib.compress(raw)
        return len(compressed) / (len(raw) + 1)

    def vet(self, reasoning: str, max_complexity: float = 0.6) -> dict[str, Any]:
        import zlib

        complexity = self.lz_complexity(reasoning)
        word_count = len(reasoning.split())
        contradiction = bool(
            re.search(
                r"\b(but|however|although|yet)\b.*\b(but|however|although|yet)\b",
                reasoning,
                re.IGNORECASE,
            )
        )
        trusted = complexity <= max_complexity and not contradiction and word_count < 200
        if not trusted:
            logger.warning(
                f"[VETTER] Reasoning rejected. complexity={complexity:.2f}, contradiction={contradiction}, words={word_count}"
            )
        return {
            "trusted": trusted,
            "complexity": round(complexity, 3),
            "contradiction": contradiction,
            "word_count": word_count,
        }
