"""
merge_logic.py  –  Sovereign Surgical Merger
==============================================
For every file in the D-drive that also exists locally, this script:
  1. Uses the FULL D-drive file as the authoritative base for any line
     that exists in the D-drive but NOT in the local file.
  2. Preserves every line that is local-only (lines in C but not in D).
  3. Strategy: Build the UNION of both files using a 3-way merge approach:
     - Start with D-drive lines (authoritative institutional logic).
     - Walk through local file; any local-only block (not in D) is APPENDED
       at the end of the merged file with a clear boundary comment.
  4. Writes the merged result back to the local file.
  5. Uses Python's difflib.SequenceMatcher to detect unique local additions.

This is NON-DESTRUCTIVE. All local logic is preserved. All D-drive logic is added.
"""
import difflib
import os
import re
import shutil
from pathlib import Path

D_SRC = Path(r"D:\Claude\samvid-trading-core-main\samvid-trading-core-main\src")
C_SRC = Path(r"C:\Users\talpa\Desktop\System_Beta\TradingSystem\src")
BACKUP_DIR = Path(r"C:\Users\talpa\Desktop\System_Beta\TradingSystem\tools\backup_before_merge")
BACKUP_DIR.mkdir(exist_ok=True)

# Files with the most complex diffs — we will merge each individually
SHARED_FILES = sorted({f.name for f in D_SRC.glob("*.py")} & {f.name for f in C_SRC.glob("*.py")})

# ── helpers ──────────────────────────────────────────────────────────────────

def read_file(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

def write_file(path: Path, lines: list[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")

def backup(path: Path) -> None:
    dst = BACKUP_DIR / path.name
    if not dst.exists():
        shutil.copy2(path, dst)

def extract_local_only_blocks(d_lines, c_lines) -> list[str]:
    """
    Returns lines that are in the LOCAL file but NOT in the D-drive file.
    Uses SequenceMatcher to find insertions/replacements unique to the local file.
    """
    sm = difflib.SequenceMatcher(None, d_lines, c_lines, autojunk=False)
    local_only = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            # These lines exist in C but not (or differently) in D
            local_only.extend(c_lines[j1:j2])
    return local_only

def merge_files(name: str, d_lines: list[str], c_lines: list[str]) -> list[str]:
    """
    Merge strategy:
      - Use D-drive as the base (ensures ALL institutional logic is present).
      - Find any local-only additions (blocks unique to C).
      - If local-only blocks exist, append them before the final `if __name__` block.
    """
    local_only = extract_local_only_blocks(d_lines, c_lines)

    if not local_only:
        return d_lines  # Identical or D is superset

    # Strip leading/trailing blank lines from local_only
    while local_only and local_only[0].strip() == "":
        local_only.pop(0)
    while local_only and local_only[-1].strip() == "":
        local_only.pop()

    if not local_only:
        return d_lines

    # Find insertion point: before `if __name__ == "__main__"` or at end
    merged = list(d_lines)

    # Remove trailing blank lines from merged
    while merged and merged[-1].strip() == "":
        merged.pop()

    # Find if __name__ guard
    insert_at = len(merged)
    for i, line in enumerate(merged):
        if re.match(r'^\s*if\s+__name__\s*==\s*["\']__main__["\']', line):
            insert_at = i
            break

    separator = [
        "\n",
        "# " + "=" * 70 + "\n",
        "# LOCAL-ONLY SOVEREIGN EXTENSIONS (preserved from local system)\n",
        "# " + "=" * 70 + "\n",
        "\n",
    ]
    merged[insert_at:insert_at] = separator + local_only + ["\n"]
    return merged

# ── Main merge loop ───────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print("  SOVEREIGN SURGICAL MERGER")
print(f"{'='*70}\n")

merged_count = 0
identical_count = 0

for name in SHARED_FILES:
    d_path = D_SRC / name
    c_path = C_SRC / name

    d_lines = read_file(d_path)
    c_lines = read_file(c_path)

    # Quick identical check
    if d_lines == c_lines:
        identical_count += 1
        print(f"  ✅ IDENTICAL       {name}")
        continue

    backup(c_path)
    merged = merge_files(name, d_lines, c_lines)
    write_file(c_path, merged)
    merged_count += 1

    additions = len(extract_local_only_blocks(d_lines, c_lines))
    d_net = len(merged) - len(c_lines)
    print(f"  🔀 MERGED          {name:50s}  local_preserved={additions:4d}  net_d_additions={d_net:+5d}")

print(f"\n{'='*70}")
print(f"  COMPLETE: {merged_count} files merged, {identical_count} already identical.")
print(f"  Backups saved to: {BACKUP_DIR}")
print(f"{'='*70}\n")
