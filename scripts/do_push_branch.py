#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
BRANCH = "fix/startup-safety-and-pattern-detection"

def run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
    return result.returncode, result.stdout, result.stderr

# Create branch from current main
rc, out, err = run(["git", "checkout", "-b", BRANCH])
print(f"git checkout -b {BRANCH}: rc={rc}")
print(out)
if err:
    print(err, file=sys.stderr)

# Push new branch
rc2, out2, err2 = run(["git", "push", "-u", "origin", BRANCH])
print(f"\ngit push: rc={rc2}")
print(out2)
if err2:
    print(err2, file=sys.stderr)

if rc2 == 0:
    print(f"\n✓ Pushed to origin/{BRANCH}")
    print(f"Create PR: https://github.com/AshishTalpada/samvid-trading-core/pull/new/{BRANCH}")
