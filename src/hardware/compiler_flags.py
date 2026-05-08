import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


class CompilerFlagsManager:
    """
    Manages native compilation flags for maximum CPU performance.
    Detects CPU capabilities and configures -march=native -O3 -ffast-math.
    Also checks for AVX-512 SIMD instruction set availability.
    """

    def detect_cpu_flags(self) -> list[str]:
        if platform.system() != "Linux":
            logger.info("[COMPILER] Non-Linux: using safe defaults")
            return ["-O2", "-std=c++17"]
        try:
            with open("/proc/cpuinfo", "r") as f:
                flags_line = next((l for l in f if l.startswith("flags")), "")
            cpu_flags = flags_line.split(":")[1].split() if ":" in flags_line else []
        except Exception:
            cpu_flags = []

        compile_flags = ["-march=native", "-O3", "-ffast-math", "-funroll-loops"]
        if "avx512f" in cpu_flags:
            compile_flags.append("-mavx512f")
            logger.info("[COMPILER] AVX-512 detected — enabling SIMD vectorisation")
        if "avx2" in cpu_flags:
            compile_flags.append("-mavx2")
        return compile_flags

    def generate_makefile_flags(self) -> str:
        flags = self.detect_cpu_flags()
        return f"CXXFLAGS = {' '.join(flags)}"
