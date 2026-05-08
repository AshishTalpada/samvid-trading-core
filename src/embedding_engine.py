import logging
import threading
from typing import Any, List, Optional, Union, cast

import numpy as np
from chromadb import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)


class SharedEmbeddingEngine:
    """
    Singleton Embedding Engine.
    Hardened for concurrent VRAM access and batch processing.
    """

    _instance: Optional["SharedEmbeddingEngine"] = None
    _model: Optional[Any] = None
    _lock = threading.Lock()

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
                logger.error(f"SharedEmbeddingEngine: Model load failed: {e}")
                return None
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Hardened Embedding Call.
        """
        model = self._get_model()
        if model is None:
            logger.critical("SharedEmbeddingEngine: MODEL NOT INITIALIZED. Vector search is BLIND.")
            return []

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
        embeddings = self.engine.embed(list(input))
        # Ensure we return the specific format Pyrefly/Chroma expects
        return cast(Embeddings, [np.array(e, dtype=np.float32) for e in embeddings])


# Globally accessible instance for ChromaDB collections
embedding_function = SovereignEmbeddingWrapper()
