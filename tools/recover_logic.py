"""
recover_logic.py
Sovereign Infrastructure Recovery Tool
Compares every Python file in the D-drive reference against the local C-drive
and produces a detailed diff report, a list of D-drive-only files (to be copied),
and a list of local-only files (to be preserved untouched).
"""

import difflib
import os
import shutil
from pathlib import Path

D_SRC = Path(r"D:\Claude\samvid-trading-core-main\samvid-trading-core-main\src")
C_SRC = Path(r"C:\Users\talpa\Desktop\System_Beta\TradingSystem\src")
REPORT_DIR = Path(r"C:\Users\talpa\Desktop\System_Beta\TradingSystem\tools\recovery_report")
REPORT_DIR.mkdir(exist_ok=True)

d_files = {f.name for f in D_SRC.glob("*.py")}
c_files = {f.name for f in C_SRC.glob("*.py")}

d_only = sorted(d_files - c_files)  # In D, missing from C → need to COPY
c_only = sorted(c_files - d_files)  # In C, not in D  → LOCAL EXCLUSIVE (preserve)
both = sorted(d_files & c_files)  # In both          → need DIFF

print(f"\n{'=' * 70}")
print("  SOVEREIGN RECOVERY SCAN")
print(f"{'=' * 70}")
print(f"  D-drive files : {len(d_files)}")
print(f"  C-drive files : {len(c_files)}")
print(f"  D-ONLY (missing from local): {len(d_only)}")
print(f"  C-ONLY (local exclusive)   : {len(c_only)}")
print(f"  SHARED (need diff)         : {len(both)}")
print(f"{'=' * 70}\n")

# ── 1. Files in D but not in C (must be COPIED) ─────────────────────────────
print("FILES MISSING FROM LOCAL (D-drive only — will be COPIED):")
for name in d_only:
    src = D_SRC / name
    dst = C_SRC / name
    shutil.copy2(src, dst)
    print(f"  ✅ COPIED  →  {name}")

# ── 2. Files in C but not in D (local exclusive — DO NOT TOUCH) ─────────────
print("\nLOCAL-EXCLUSIVE FILES (not in D-drive — preserved untouched):")
for name in c_only:
    print(f"  🛡️  PRESERVE  →  {name}")

# ── 3. Files in both → diff and report ──────────────────────────────────────
print(f"\nCOMPARING {len(both)} SHARED FILES…\n")

changed_files = []
identical_files = []

for name in both:
    d_path = D_SRC / name
    c_path = C_SRC / name

    d_lines = d_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    c_lines = c_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(c_lines, d_lines, fromfile=f"LOCAL/{name}", tofile=f"D-DRIVE/{name}")
    )

    if not diff:
        identical_files.append(name)
    else:
        changed_files.append(name)
        # Count additions (lines in D not in C)
        additions = [l for l in diff if l.startswith("+") and not l.startswith("+++")]
        deletions = [l for l in diff if l.startswith("-") and not l.startswith("---")]
        print(
            f"  ⚠️  {name:45s}  +{len(additions):4d} lines from D  -{len(deletions):4d} local lines"
        )
        # Save diff file
        diff_file = REPORT_DIR / f"{name}.diff"
        diff_file.write_text("".join(diff), encoding="utf-8")

print(f"\n  ✅ Identical files : {len(identical_files)}")
print(f"  ⚠️  Files with diffs: {len(changed_files)}")
print(f"\nDiff files saved to: {REPORT_DIR}")
print("\nFILES WITH DIFFS:")
for name in changed_files:
    print(f"  → {name}")

# ── Write master summary ─────────────────────────────────────────────────────
summary_path = REPORT_DIR / "RECOVERY_SUMMARY.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    f.write("SOVEREIGN RECOVERY SUMMARY\n")
    f.write("=" * 60 + "\n\n")
    f.write("D-ONLY (COPIED to local):\n")
    for n in d_only:
        f.write(f"  {n}\n")
    f.write("\nC-ONLY (PRESERVED - local exclusive):\n")
    for n in c_only:
        f.write(f"  {n}\n")
    f.write("\nFILES WITH DIFFS (need manual review):\n")
    for n in changed_files:
        f.write(f"  {n}\n")
    f.write("\nIDENTICAL FILES:\n")
    for n in identical_files:
        f.write(f"  {n}\n")

print(f"\nMaster summary written to: {summary_path}")
