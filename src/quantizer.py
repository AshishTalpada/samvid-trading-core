import logging

import numpy as np

logger = logging.getLogger(__name__)


class ModelQuantizer:
    """
    Dynamic model precision switcher.
    Drops to INT8 quantization for latency-critical fast trades,
    restores FP32 for deep fundamental analysis where precision matters.
    """

    def __init__(self):
        self.current_precision = "FP32"

    def quantize_weights(self, weights: np.ndarray, bits: int = 8) -> np.ndarray:
        w_min, w_max = weights.min(), weights.max()
        scale = (w_max - w_min) / (2**bits - 1)
        quantized = np.round((weights - w_min) / scale).astype(np.int32)
        return quantized  # type: ignore

    def dequantize(
        self, quantized: np.ndarray, w_min: float, w_max: float, bits: int = 8
    ) -> np.ndarray:
        scale = (w_max - w_min) / (2**bits - 1)
        return quantized.astype(np.float32) * scale + w_min  # type: ignore

    def switch_precision(self, mode: str) -> None:
        if mode not in ("INT8", "FP32", "FP16"):
            raise ValueError(f"Unknown precision: {mode}")
        self.current_precision = mode
        logger.info(f"[QUANTIZER] Precision switched to {mode}")

    def quantization_error(self, original: np.ndarray, bits: int = 8) -> float:
        q = self.quantize_weights(original, bits)
        dq = self.dequantize(q, float(original.min()), float(original.max()), bits)
        return float(np.mean(np.abs(original - dq)))
