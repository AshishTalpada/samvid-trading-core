import logging
import threading
from typing import Optional, List
from chromadb import Documents, EmbeddingFunction, Embeddings

logger = logging.getLogger(__name__)

class SharedEmbeddingEngine:
    """
    SETO V21.50: Singleton Embedding Engine.
    Hardened for concurrent VRAM access and batch processing (GAP-73/75/76).
    """
    _instance: Optional['SharedEmbeddingEngine'] = None
    _model: Optional[any] = None
    _lock = threading.Lock() # GAP-73: Global VRAM access lock

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
                
                # GAP-206 FIX: swappable model from Vault
                model_name = Vault.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
                self._model = TextEmbedding(model_name)
                logger.info(f"✓ SharedEmbeddingEngine: {model_name} loaded into memory.")
            except Exception as e:
                logger.error(f"SharedEmbeddingEngine: Model load failed: {e}")
                return None
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Hardened Embedding Call (GAP-75 Batching & GAP-73 Locking).
        """
        model = self._get_model()
        if model is None:
            # GAP-76: Avoid silent fail by notifying the log with CRITICAL
            logger.critical("SharedEmbeddingEngine: MODEL NOT INITIALIZED. Vector search is BLIND.")
            return []

        # GAP-75: Automatic Batching (Max 100 items per batch for Chroma/Memory safety)
        BATCH_SIZE = 100
        all_embeddings = []

        with self._lock: # GAP-73: Ensure serialized VRAM access
            try:
                for i in range(0, len(texts), BATCH_SIZE):
                    batch = texts[i:i + BATCH_SIZE]
                    # fastembed returns a generator
                    batch_gen = model.embed(batch)
                    batch_list = [[float(val) for val in vec] for vec in batch_gen]
                    all_embeddings.extend(batch_list)
                
                return all_embeddings
            except Exception as e:
                # GAP-76: Hardening failure notification
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
