#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent

def run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
    return result.returncode, result.stdout, result.stderr

# Check current branch
rc, out, err = run(["git", "branch", "--show-current"])
print(f"Current branch: {out.strip()}")

# Check remote branches
rc2, out2, err2 = run(["git", "branch", "-r"])
print(f"Remote branches:\n{out2}")

# Push current branch to origin
rc3, out3, err3 = run(["git", "push", "origin", out.strip()])
print(f"\ngit push: rc={rc3}")
print(out3)
if err3:
    print(err3, file=sys.stderr)
