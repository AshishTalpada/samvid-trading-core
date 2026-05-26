#!/usr/bin/env python3
"""Sync with remote and push current branch."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent

def run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
    return result.returncode, result.stdout, result.stderr

print("=" * 60)
print("GIT SYNC AND PUSH")
print("=" * 60)

# 1. Get current branch
rc, branch, err = run(["git", "branch", "--show-current"])
branch = branch.strip()
print(f"\nCurrent branch: {branch}")

# 2. Fetch from origin
print("\n[1/4] Fetching from origin...")
rc, out, err = run(["git", "fetch", "origin"])
if rc != 0:
    print(f"Fetch failed: {err}")
    sys.exit(1)
print("Fetch OK")

# 3. Check status
print("\n[2/4] Checking status...")
rc, out, err = run(["git", "status", "-sb"])
print(out)

# 4. Check if behind
print("\n[3/4] Checking if behind origin...")
rc, out, err = run(["git", "rev-list", "HEAD..origin/main", "--count"])
behind_main = int(out.strip()) if out.strip().isdigit() else 0
print(f"Commits behind origin/main: {behind_main}")

if behind_main > 0:
    print(f"WARNING: {behind_main} commits behind origin/main")
    print("You may want to rebase or merge origin/main first.")
    print("\nTo merge origin/main into this branch:")
    print("  git merge origin/main")

# Check if current branch has remote
rc, out, err = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
if rc != 0:
    print("\n[4/4] No upstream set. Setting upstream...")
    rc2, out2, err2 = run(["git", "push", "-u", "origin", branch])
    print(f"Push result: rc={rc2}")
    print(out2)
    if err2:
        print(err2)
else:
    upstream = out.strip()
    print(f"\n[4/4] Pushing to {upstream}...")
    rc2, out2, err2 = run(["git", "push"])
    print(f"Push result: rc={rc2}")
    print(out2)
    if err2:
        print(err2)

# Final status
print("\n" + "=" * 60)
print("FINAL STATUS")
print("=" * 60)
rc, out, err = run(["git", "status", "-sb"])
print(out)
print("\nDone.")
