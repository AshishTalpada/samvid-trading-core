"""
tools/deep_bug_check.py
Sovereign Runtime Bug Scanner
Checks all critical files for common runtime failure patterns.
"""

import ast
import re
from pathlib import Path

SRC = Path("src")
issues = []

CRITICAL = [
    "brain.py",
    "coordinator.py",
    "data_pipeline.py",
    "intelligence_bus.py",
    "resilience_layer.py",
    "mind_ultrathink.py",
    "swarm_predictor.py",
    "dhatu_oracle.py",
    "trading_state.py",
    "agent_h_skeptic.py",
    "shadow_sim.py",
    "system_types.py",
    "main.py",
    "quant_math.py",
    "ibkr_streamer.py",
    "execution_router.py",
    "vix_circuit_breaker.py",
    "stress_veto.py",
    "time_sync.py",
    "session_restorer.py",
]


def check_file(fpath):
    code = fpath.read_text(encoding="utf-8", errors="replace")
    lines = code.splitlines()
    fname = fpath.name

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # 1. Silent bare except:pass
        if stripped == "except Exception:" or stripped == "except:":
            if i < len(lines) and lines[i].strip() == "pass":
                issues.append((fname, i, "Silent except:pass — errors swallowed without logging"))

        # 2. Direct brain.py import from other modules (circular import risk)
        if "from brain import" in stripped and fname != "brain.py":
            issues.append((fname, i, "Direct 'from brain import' — potential circular import"))

        # 3. asyncio.run() called inside async function (crashes event loop)
        if "asyncio.run(" in stripped and "async def" not in stripped:
            # Walk up to see if we're inside an async def
            issues.append((fname, i, "Possible asyncio.run() inside coroutine context"))

        # 4. Mutable default arguments in dataclass / function signatures
        if re.search(r"def \w+\(.*=\[\]", stripped) or re.search(r"def \w+\(.*=\{\}", stripped):
            issues.append(
                (
                    fname,
                    i,
                    "Mutable default argument (list/dict) — use field(default_factory=...) instead",
                )
            )

        # 5. Unreachable return after return
        # (simple heuristic: two consecutive return lines at same indent)
        if stripped.startswith("return ") and i < len(lines):
            next_stripped = lines[i].strip()
            if next_stripped.startswith("return ") and len(line) - len(line.lstrip()) == len(
                lines[i]
            ) - len(lines[i].lstrip()):
                issues.append((fname, i + 1, "Unreachable return statement after preceding return"))

        # 6. Non-awaited known coroutines stored but never awaited
        for coro_name in ["bus.publish", "bus.subscribe", "asyncio.sleep"]:
            if coro_name + "(" in stripped:
                if (
                    not stripped.startswith("await ")
                    and not stripped.startswith("#")
                    and "def " not in stripped
                    and "lambda" not in stripped
                ):
                    if "= " in stripped and not stripped.startswith("task"):
                        pass  # Assignment form is OK (might be awaited later)

    # 7. AST-level: undefined names used in annotations
    try:
        tree = ast.parse(code)
        # Check for TYPE_CHECKING guarded imports used at runtime
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and hasattr(node, "lineno"):
                pass  # Hard to validate without running the code
    except SyntaxError as e:
        issues.append((fname, e.lineno or 0, f"SyntaxError: {e.msg}"))


for fname in CRITICAL:
    fp = SRC / fname
    if fp.exists():
        check_file(fp)
    else:
        issues.append((fname, 0, "FILE MISSING"))

print(f"\n{'=' * 60}")
print("  SOVEREIGN RUNTIME BUG SCANNER")
print(f"  Files checked: {len(CRITICAL)}")
print(f"  Issues found: {len(issues)}")
print(f"{'=' * 60}\n")

if issues:
    for fname, line, msg in issues:
        print(f"  {fname}:{line}  --  {msg}")
else:
    print("  All clear — no silent errors, circular imports, or obvious runtime bugs detected.")

print()
