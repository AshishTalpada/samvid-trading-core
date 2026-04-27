"""
scripts/build_optimized.py
==========================
Compiles the Trading System to a standalone high-performance binary
using Nuitka (Python → C++ → Machine Code).

Benefits:
  - Eliminates interpreter overhead: ~2-4x CPU-bound speedup
  - Faster startup time
  - Single .exe distribution (no Python install needed on target)

Prerequisites:
  pip install nuitka
  # Windows: also needs a C compiler — MinGW64 or MSVC
  # Install MinGW64: https://www.mingw-w64.org/downloads/

Usage:
  python scripts/build_optimized.py
  # Output: dist/TradingSystem.exe
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRY = ROOT / "src" / "main.py"
DIST  = ROOT / "dist"

NUITKA_ARGS = [
    sys.executable, "-m", "nuitka",
    # === Output ===
    "--standalone",             # Bundle everything into a self-contained dir
    "--onefile",                # Compress into a single .exe
    f"--output-dir={DIST}",
    "--output-filename=TradingSystem",

    # === Compiler ===
    # "--mingw64",              # Removed for Python 3.13+ compatibility

    # === Critical Plugins ===
    # "--enable-plugin=numpy",   # Deprecated in Nuitka 4.0+
    # "--enable-plugin=upx",     # Removed to avoid "UPX not found" error

    # === Follow Imports ===
    "--follow-imports",         # Include all project imports
    "--include-package=src",
    "--include-package=ib_insync",
    "--include-package=winloop",

    # === Optimization Level ===
    "--lto=yes",               # Link-Time Optimization for max speed
    "--jobs=4",                # Parallel compile jobs

    # === Remove Debug ===
    "--python-flag=no_docstrings",  # Strip docstrings from binary
    "--python-flag=-O",             # Python -O optimization flag

    # === Automate Downloads ===
    "--assume-yes-for-downloads",   # Don't ask for permission to download CC/UPX
    
    # === Entry ===
    str(ENTRY),
]

if __name__ == "__main__":
    DIST.mkdir(exist_ok=True)
    print("=" * 60)
    print("Trading System V3.0 — HPC Nuitka Build")
    print("=" * 60)
    print(f"\nEntry: {ENTRY}")
    print(f"Output: {DIST / 'TradingSystem.exe'}")
    print("\nStarting compilation (this takes 5-15 minutes)...\n")

    result = subprocess.run(NUITKA_ARGS, cwd=ROOT)

    if result.returncode == 0:
        print("\n✓ Build successful!")
        print(f"  Executable: {DIST / 'TradingSystem.exe'}")
        print("\nRun with:")
        print(f"  {DIST / 'TradingSystem.exe'}")
    else:
        print(f"\n✗ Build failed (exit code: {result.returncode})")
        print("Common fixes:")
        print("  pip install nuitka")
        print("  Install MinGW64 from https://www.mingw-w64.org/downloads/")
        sys.exit(result.returncode)
