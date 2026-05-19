import ctypes
import logging
import os
from pathlib import Path

logger = logging.getLogger("NativeLoader")


class NativeLibrary:
    _instance = None
    _lib = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NativeLibrary, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        try:
            # Detect OS and extension
            ext = ".dll" if os.name == "nt" else ".so"
            # Search in build/ and root/
            possible_paths = [
                Path("build") / f"libsovereign{ext}",
                Path(f"libsovereign{ext}"),
                Path("src") / f"libsovereign{ext}",
            ]

            for path in possible_paths:
                if path.exists():
                    self._lib = ctypes.CDLL(str(path.absolute()))
                    logger.info(f" Native library loaded from {path}")

                    # Define argument/return types for safety core
                    if hasattr(self._lib, "set_global_halt"):
                        self._lib.set_global_halt.argtypes = [ctypes.c_bool]
                        self._lib.set_global_halt.restype = None

                    if hasattr(self._lib, "is_global_halt_active"):
                        self._lib.is_global_halt_active.argtypes = []
                        self._lib.is_global_halt_active.restype = ctypes.c_bool

                    if hasattr(self._lib, "get_latest_telemetry"):
                        self._lib.get_latest_telemetry.argtypes = []
                        self._lib.get_latest_telemetry.restype = NativeTelemetry

                    return

            logger.warning(
                "Native library libsovereign not found. Native optimizations and safety signals disabled."
            )
        except Exception as e:
            logger.error(f"Failed to load native library: {e}")

    def set_halt(self, state: bool):
        if self._lib and hasattr(self._lib, "set_global_halt"):
            self._lib.set_global_halt(state)

    def is_halted(self) -> bool:
        if self._lib and hasattr(self._lib, "is_global_halt_active"):
            return self._lib.is_global_halt_active()
        return False

    def get_telemetry(self) -> dict:
        if self._lib and hasattr(self._lib, "get_latest_telemetry"):
            t = self._lib.get_latest_telemetry()
            return {
                "latency_ms": t.execution_latency_ms,
                "slippage_bps": t.slippage_bps,
                "fill_count": t.fill_count,
                "hardware_fault": t.hardware_fault,
            }
        return {}


class NativeTelemetry(ctypes.Structure):
    _fields_ = [
        ("execution_latency_ms", ctypes.c_double),
        ("slippage_bps", ctypes.c_double),
        ("fill_count", ctypes.c_int),
        ("hardware_fault", ctypes.c_bool),
    ]


# Singleton instance
NATIVE = NativeLibrary()
