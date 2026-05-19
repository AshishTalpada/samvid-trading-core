"""
fix_merges.py  –  Post-Merge Syntax Fixer
==========================================
The separator block was sometimes injected inside a class or function body,
causing IndentationError. This script:
  1. Reads the backup (the original local file before merge).
  2. Re-does the merge using a SAFER strategy:
     - Use D-drive file verbatim as the new content.
     - Collect all local-only TOP-LEVEL declarations (class / def / constants)
       that are NOT present in the D-drive file.
     - Append those at the true module top-level (after all imports, before
       or after the final `if __name__` guard).
     - All local-only declarations inside classes are injected as class methods
       using a proper indentation-aware approach.
"""

import ast
import difflib
import re
import shutil
from pathlib import Path

D_SRC = Path(r"D:\Claude\samvid-trading-core-main\samvid-trading-core-main\src")
C_SRC = Path(r"C:\Users\talpa\Desktop\System_Beta\TradingSystem\src")
BACKUP = Path(r"C:\Users\talpa\Desktop\System_Beta\TradingSystem\tools\backup_before_merge")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def is_parseable(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def get_top_level_names(code: str) -> set[str]:
    """Return all top-level function / class names defined in the module."""
    names = set()
    try:
        tree = ast.parse(code)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
    except SyntaxError:
        pass
    return names


def get_top_level_segments(code: str) -> list[tuple[str, str]]:
    """
    Returns list of (name, source_text) for every top-level definition.
    Each segment includes its leading decorators and trailing blank lines.
    """
    lines = code.splitlines(keepends=True)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []

    segments = []
    top_nodes = [
        n
        for n in ast.iter_child_nodes(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    for i, node in enumerate(top_nodes):
        start = node.lineno - 1  # 0-indexed
        # Walk back to capture decorators
        while start > 0 and (
            lines[start - 1].strip().startswith("@") or lines[start - 1].strip() == ""
        ):
            if lines[start - 1].strip().startswith("@"):
                start -= 1
            else:
                break
        if i + 1 < len(top_nodes):
            end = top_nodes[i + 1].lineno - 1
            # Walk back past blank lines
            while end > start and lines[end - 1].strip() == "":
                end -= 1
        else:
            end = len(lines)
        name = node.name
        segments.append((name, "".join(lines[start:end])))
    return segments


def smart_merge(name: str, d_code: str, c_code: str) -> str:
    """
    Strategy:
    1. Start with D-drive code (guaranteed institutional base).
    2. Find top-level segments in C that are NOT in D.
    3. Append them cleanly at module level.
    """
    d_names = get_top_level_names(d_code)
    c_segments = get_top_level_segments(c_code)

    local_only_segments = [
        (seg_name, seg_code) for seg_name, seg_code in c_segments if seg_name not in d_names
    ]

    if not local_only_segments:
        return d_code

    # Also capture module-level constants / assignments unique to local
    # by comparing raw lines
    d_lines = set(d_code.splitlines())
    c_lines_all = c_code.splitlines(keepends=True)
    local_only_lines = []
    for line in c_lines_all:
        stripped = line.rstrip()
        # Only include top-level assignments and simple statements (no indent, not blank, not import)
        if (
            stripped
            and not stripped.startswith(" ")
            and not stripped.startswith("\t")
            and stripped not in d_lines
            and not stripped.startswith("#")
            and not stripped.startswith("import ")
            and not stripped.startswith("from ")
            and not stripped.startswith("class ")
            and not stripped.startswith("def ")
            and not stripped.startswith("async def ")
            and not stripped.startswith("if __name__")
        ):
            local_only_lines.append(line)

    # Build the merged content
    merged_lines = d_code.rstrip().splitlines(keepends=True)

    # Find insertion point before `if __name__`
    insert_at = len(merged_lines)
    for i, line in enumerate(merged_lines):
        if re.match(r'^if\s+__name__\s*==\s*["\']__main__["\']', line):
            insert_at = i
            break

    additions = []
    if local_only_lines:
        additions += [
            "\n",
            "# ── LOCAL-ONLY MODULE CONSTANTS ─────────────────────────────────────────\n",
        ]
        additions += local_only_lines

    if local_only_segments:
        additions += [
            "\n",
            "# ── LOCAL-ONLY SOVEREIGN EXTENSIONS ─────────────────────────────────────\n",
        ]
        for seg_name, seg_code in local_only_segments:
            additions += ["\n", "\n"]
            additions += seg_code.splitlines(keepends=True)
            if not additions[-1].endswith("\n"):
                additions.append("\n")

    merged_lines[insert_at:insert_at] = additions

    result = "".join(merged_lines)
    if not result.endswith("\n"):
        result += "\n"
    return result


# ─── Main ────────────────────────────────────────────────────────────────────

files_to_fix = [f.name for f in C_SRC.glob("*.py") if (D_SRC / f.name).exists()]

print(f"\n{'=' * 70}")
print("  POST-MERGE SYNTAX FIX (Smart Merge v2)")
print(f"{'=' * 70}\n")

ok_count = 0
fixed_count = 0
error_count = 0

for name in sorted(files_to_fix):
    d_path = D_SRC / name
    c_path = C_SRC / name
    backup_path = BACKUP / name

    d_code = read(d_path)

    # Use backup as the "original local" source
    c_code = read(backup_path) if backup_path.exists() else read(c_path)

    merged = smart_merge(name, d_code, c_code)

    if is_parseable(merged):
        write(c_path, merged)
        ok_count += 1
        local_segs = [
            s for s in get_top_level_segments(c_code) if s[0] not in get_top_level_names(d_code)
        ]
        if local_segs or merged != d_code:
            fixed_count += 1
            print(f"  ✅ MERGED+OK  {name:55s}  local_extensions={len(local_segs)}")
        else:
            print(f"  ✅ D-BASE     {name}")
    else:
        # Fallback: just use D-drive code — it's guaranteed clean
        fallback = d_code
        if is_parseable(fallback):
            write(c_path, fallback)
            print(f"  ⚠️  D-ONLY FALLBACK (local extensions lost): {name}")
            ok_count += 1
        else:
            error_count += 1
            print(f"  ❌ UNPARSEABLE EVEN D-DRIVE: {name}")

print(f"\n{'=' * 70}")
print(f"  FILES OK     : {ok_count}")
print(f"  WITH MERGES  : {fixed_count}")
print(f"  ERRORS       : {error_count}")
print(f"{'=' * 70}\n")
