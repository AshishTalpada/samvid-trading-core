"""Build the optional native acceleration and safety library."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "build" / ("libsovereign.dll" if sys.platform == "win32" else "libsovereign.so")
SOURCES = (
    ROOT / "src" / "heartbeat.c",
    ROOT / "quarantine" / "time_sync.c",
    ROOT / "src" / "memory_guard.c",
    ROOT / "src" / "hardware_audit.c",
    ROOT / "src" / "safety_core.c",
    ROOT / "src" / "chaos_metrics.cpp",
    ROOT / "src" / "agent_a_simd.cpp",
    ROOT / "quarantine" / "rng_audit.cpp",
)


def _find_vcvarsall() -> Path:
    visual_studio_root = (
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        / "Microsoft Visual Studio"
    )
    candidates = sorted(
        visual_studio_root.glob("*/*/VC/Auxiliary/Build/vcvarsall.bat"),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("Visual Studio Build Tools vcvarsall.bat was not found")
    return candidates[0]


def _windows_command(vcvarsall: Path) -> str:
    sources = " ".join(f'"{source}"' for source in SOURCES)
    return (
        f'call "{vcvarsall}" x64\n'
        "if errorlevel 1 exit /b %errorlevel%\n"
        "cl /O2 /std:c11 /experimental:c11atomics /LD "
        f'/Fe:"{TARGET}" {sources} /I"{ROOT / "src"}"\n'
    )


def build_native() -> int:
    missing = [str(source) for source in SOURCES if not source.exists()]
    if missing:
        raise FileNotFoundError(f"Native source files missing: {', '.join(missing)}")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        result = subprocess.run(
            ["cmd.exe", "/d", "/q"],
            cwd=ROOT,
            check=False,
            input=_windows_command(_find_vcvarsall()),
            text=True,
        )
    else:
        result = subprocess.run(["make", "all"], cwd=ROOT, check=False)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(build_native())
