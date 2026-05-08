import numpy as np


class HolographicMemory:
    def __init__(self, dim: int = 1024):
        self.dim = dim
        self.memory = np.zeros(dim)

    def store(self, key_vec: np.ndarray, val_vec: np.ndarray):
        self.memory += np.fft.ifft(np.fft.fft(key_vec) * np.fft.fft(val_vec)).real

    def retrieve(self, key_vec: np.ndarray) -> np.ndarray:
        inv_key = np.roll(key_vec[::-1], 1)
        return np.fft.ifft(np.fft.fft(inv_key) * np.fft.fft(self.memory)).real
