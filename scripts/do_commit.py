#!/usr/bin/env python3
"""Git commit helper — avoids shell quoting issues."""
import subprocess
import sys
from pathlib import Path

def run(cmd: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr

root = Path(__file__).resolve().parent.parent
print(f"Project root: {root}")

# Add all changes
rc, out, err = run(["git", "add", "-A"], cwd=str(root))
print(f"git add: rc={rc}")
if out:
    print(out)
if err:
    print(err, file=sys.stderr)

# Commit
msg = """fix: 6 more critical bugs — pattern detection, async safety, Agent D vetoes

- agent_a: fix UNCONFIRMED_PENALTY inconsistency (hardcoded -10 → config -5)
- agent_a: volatility breakout 0.2% absolute → relative squeeze vs median bands
- intelligence_bus: fix weakref.finalize race condition (GC thread mutating dict)
- intelligence_bus: fix off() no-op (never removed callbacks from weak ref list)
- coordinator+resilience_layer: Agent D veto now requires n>=30 sample size
- main: prevent live trading hang in non-TTY environments (services, scheduled tasks)
- scripts: add startup_diagnostic.py pre-flight checklist"""

rc, out, err = run(["git", "commit", "-m", msg], cwd=str(root))
print(f"git commit: rc={rc}")
print(out)
if err:
    print(err, file=sys.stderr)

# Push
rc, out, err = run(["git", "push", "origin", "merge/all-branches"], cwd=str(root))
print(f"git push: rc={rc}")
print(out)
if err:
    print(err, file=sys.stderr)

print("\nDone.")
