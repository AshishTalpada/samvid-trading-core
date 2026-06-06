"""Build the optional native acceleration and safety library."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath

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


def _windows_command(vcvarsall: Path, target: Path = TARGET) -> str:
    sources = " ".join(f'"{PureWindowsPath(source.relative_to(ROOT))}"' for source in SOURCES)
    return (
        f'call "{vcvarsall}" x64\n'
        "if errorlevel 1 exit /b %errorlevel%\n"
        "cl /O2 /std:c11 /experimental:c11atomics /LD "
        f'/Fe:"{PureWindowsPath(target)}" {sources} /I"src"\n'
        "if errorlevel 1 exit /b %errorlevel%\n"
    )


def _windows_fallback_target() -> Path:
    return ROOT / "build" / "native_builds" / f"libsovereign_{time.time_ns()}.dll"


def build_native() -> int:
    missing = [str(source) for source in SOURCES if not source.exists()]
    if missing:
        raise FileNotFoundError(f"Native source files missing: {', '.join(missing)}")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        vcvarsall = _find_vcvarsall()
        result = subprocess.run(
            ["cmd.exe", "/d", "/q"],
            cwd=ROOT,
            check=False,
            input=_windows_command(vcvarsall, TARGET),
            text=True,
        )
        if result.returncode != 0 and TARGET.exists():
            fallback_target = _windows_fallback_target()
            fallback_target.parent.mkdir(parents=True, exist_ok=True)
            print(
                "Primary native DLL may be locked by a running process; "
                f"retrying link as {fallback_target}",
                file=sys.stderr,
            )
            result = subprocess.run(
                ["cmd.exe", "/d", "/q"],
                cwd=ROOT,
                check=False,
                input=_windows_command(vcvarsall, fallback_target),
                text=True,
            )
    else:
        result = subprocess.run(["make", "all"], cwd=ROOT, check=False)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(build_native())
