import numpy as np


class VoiceIDLock:
    """Only YOUR voice can authorize max-risk trades."""
    def __init__(self, owner_voice_embedding: np.ndarray):
        self.owner_embedding = owner_voice_embedding

    def authorize(self, mic_embedding: np.ndarray, threshold: float = 0.85) -> bool:
        # Cosine similarity between live mic and owner profile
        dot = np.dot(self.owner_embedding, mic_embedding)
        norm_a = np.linalg.norm(self.owner_embedding)
        norm_b = np.linalg.norm(mic_embedding)
        similarity = dot / (norm_a * norm_b + 1e-9)
        return similarity >= threshold
