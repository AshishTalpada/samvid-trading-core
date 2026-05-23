import hashlib
import logging
import threading
from typing import List, Optional

from chromadb import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)


class SharedEmbeddingEngine:
    """
    Singleton Embedding Engine.
    Hardened for concurrent VRAM access and batch processing.
    """

    _instance: Optional["SharedEmbeddingEngine"] = None
    _model: Optional[any] = None
    _lock = threading.Lock()
    _fallback_logged = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SharedEmbeddingEngine, cls).__new__(cls)
        return cls._instance

    def _get_model(self):
        if self._model is None:
            try:
                import importlib

                from vault import Vault

                fastembed = importlib.import_module("fastembed")
                TextEmbedding = fastembed.TextEmbedding

                model_name = Vault.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
                self._model = TextEmbedding(model_name)
                logger.info(f"✓ SharedEmbeddingEngine: {model_name} loaded into memory.")
            except Exception as e:
                if not self._fallback_logged:
                    logger.info(
                        "SharedEmbeddingEngine: fastembed unavailable (%s). "
                        "Using deterministic hash embeddings until dependency is installed.",
                        e,
                    )
                    self._fallback_logged = True
                return None
        return self._model

    @staticmethod
    def _hash_embedding(text: str, dims: int = 384) -> list[float]:
        values: list[float] = []
        seed = text.encode("utf-8", errors="ignore") or b"\x00"
        counter = 0
        while len(values) < dims:
            digest = hashlib.blake2b(seed + counter.to_bytes(4, "little"), digest_size=32).digest()
            values.extend(((byte / 127.5) - 1.0) for byte in digest)
            counter += 1
        return values[:dims]

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Hardened Embedding Call.
        """
        model = self._get_model()
        if model is None:
            return [self._hash_embedding(text) for text in texts]

        BATCH_SIZE = 100
        all_embeddings = []

        with self._lock:
            try:
                for i in range(0, len(texts), BATCH_SIZE):
                    batch = texts[i : i + BATCH_SIZE]
                    # fastembed returns a generator
                    batch_gen = model.embed(batch)
                    batch_list = [[float(val) for val in vec] for vec in batch_gen]
                    all_embeddings.extend(batch_list)

                return all_embeddings
            except Exception as e:
                logger.error(f"SharedEmbeddingEngine: Critical embedding failure: {e}")
                # Reset model on failure to force reload (Self-Healing)
                self._model = None
                return []


class SovereignEmbeddingWrapper(EmbeddingFunction):
    """
    ChromaDB compatible wrapper for the SharedEmbeddingEngine.
    """

    def __init__(self):
        self.engine = SharedEmbeddingEngine()

    def __call__(self, input: Documents) -> Embeddings:
        return self.engine.embed(list(input))


# Globally accessible instance for ChromaDB collections
embedding_function = SovereignEmbeddingWrapper()
