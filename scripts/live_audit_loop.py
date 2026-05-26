#!/usr/bin/env python3
"""
Live Audit Loop — runs main.py, captures output, summarises errors/warnings.
Usage:
    python scripts/live_audit_loop.py            # run once (90s)
    python scripts/live_audit_loop.py --cycles 5 # run 5 cycles
"""
import argparse
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _kill_existing_engine() -> None:
    """Kill any running main.py instances to prevent duplicate-instance errors."""
    sentinel = ROOT / ".session.bin"
    pid = None
    if sentinel.exists():
        try:
            import struct
            data = sentinel.read_bytes()
            if len(data) >= 4:
                pid = struct.unpack_from("<I", data, 0)[0]
        except Exception:
            pass

    # Also scan running processes for python main.py
    try:
        r = subprocess.run(
            ["wmic", "process", "where",
             "name='python.exe'", "get", "processid,commandline"],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            if "main.py" in line and "live_audit_loop" not in line:
                parts = line.strip().split()
                try:
                    candidate = int(parts[-1])
                    if candidate != os.getpid():
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(candidate)],
                            capture_output=True,
                        )
                        print(f"  [KILL] Terminated stale engine PID {candidate}")
                except Exception:
                    pass
    except Exception:
        pass

    if pid and pid != os.getpid():
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


def run_cycle(cycle: int, duration: int = 90) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"audit_cycle_{cycle:03d}_{ts}.log"

    print(f"\n{'='*70}")
    print(f"CYCLE {cycle:03d} | {datetime.now().strftime('%H:%M:%S')} | log → {log_path.name}")
    print(f"{'='*70}")

    _kill_existing_engine()
    time.sleep(2)  # Let ports/sockets release

    with open(log_path, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "src" / "main.py")],
            stdout=fh,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            encoding="utf-8",
            errors="replace",
        )
        try:
            proc.wait(timeout=duration)
        except subprocess.TimeoutExpired:
            print(f"  [{duration}s elapsed] Killing process {proc.pid}...")
            proc.kill()
            proc.wait()

    print(f"  Process ended. Analysing {log_path.name} ...")
    return log_path


IGNORE_PATTERNS = [
    r"^$",
    r"^\s+$",
    r"heartbeat confirmed",
    r"fetched \d+ news items",
    r"NEWS \[",
    r"Frontend connected",
    r"TIGHTEN:.*stop",
    r"Regime:",
]

_IGNORE_RE = [re.compile(p, re.IGNORECASE) for p in IGNORE_PATTERNS]

ERROR_RE = re.compile(r"\b(ERROR|CRITICAL|Exception|Traceback|raise |assert )\b", re.IGNORECASE)
WARN_RE  = re.compile(r"\bWARNING\b", re.IGNORECASE)
OFFLINE_RE = re.compile(
    r"(offline|not connected|connection (failed|refused|lost|closed)|"
    r"failed to connect|unable to connect|timeout|timed out|"
    r"IBKR.*not|MT5.*not|Dhatu.*not|OpenBB.*not|SLM.*not)",
    re.IGNORECASE,
)
SERVICE_RE = re.compile(
    r"(IBKR|MT5|Dhatu|OpenBB|SLM|QuestDB|MindGhost|Oracle|Telegram)", re.IGNORECASE
)


def analyse(log_path: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    offline: list[str] = []
    tracebacks: list[str] = []
    service_status: dict[str, list[str]] = defaultdict(list)

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip noise
        if any(p.search(line) for p in _IGNORE_RE):
            i += 1
            continue

        # Capture full traceback blocks
        if "Traceback (most recent call last)" in line:
            tb = [line]
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t") or re.match(r"\w+Error|Exception", lines[i])):
                tb.append(lines[i])
                i += 1
            tracebacks.append("\n".join(tb[-10:]))  # last 10 lines of traceback
            continue

        if ERROR_RE.search(line):
            errors.append(line.strip())
        elif WARN_RE.search(line):
            warnings.append(line.strip())

        if OFFLINE_RE.search(line):
            offline.append(line.strip())

        m = SERVICE_RE.search(line)
        if m:
            svc = m.group(1).upper()
            service_status[svc].append(line.strip())

        i += 1

    return {
        "errors": errors,
        "warnings": warnings,
        "offline": offline,
        "tracebacks": tracebacks,
        "service_status": service_status,
        "total_lines": len(lines),
    }


def print_report(cycle: int, result: dict) -> None:
    print(f"\n--- CYCLE {cycle:03d} REPORT ---")
    print(f"  Lines processed : {result['total_lines']}")
    print(f"  Errors          : {len(result['errors'])}")
    print(f"  Warnings        : {len(result['warnings'])}")
    print(f"  Offline alerts  : {len(result['offline'])}")
    print(f"  Tracebacks      : {len(result['tracebacks'])}")

    if result["tracebacks"]:
        print("\n  [TRACEBACKS]")
        for tb in result["tracebacks"][:5]:
            print("  " + "\n  ".join(tb.splitlines()))
            print()

    if result["errors"]:
        print("\n  [TOP ERRORS]")
        seen = set()
        for e in result["errors"]:
            key = e[-80:]
            if key not in seen:
                seen.add(key)
                print(f"  {e[:120]}")

    if result["warnings"]:
        print("\n  [TOP WARNINGS] (first 10 unique)")
        seen = set()
        count = 0
        for w in result["warnings"]:
            key = w[-80:]
            if key not in seen:
                seen.add(key)
                print(f"  {w[:120]}")
                count += 1
                if count >= 10:
                    break

    if result["offline"]:
        print("\n  [OFFLINE / CONNECTION ALERTS]")
        for o in result["offline"][:10]:
            print(f"  {o[:120]}")

    if result["service_status"]:
        print("\n  [SERVICE MENTIONS]")
        for svc, mentions in result["service_status"].items():
            print(f"  {svc}: {len(mentions)} log line(s)")

    print()


def save_summary(results: list[dict], log_paths: list[Path]) -> None:
    summary_path = LOG_DIR / f"audit_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"LIVE AUDIT SUMMARY — {datetime.now()}\n")
        f.write(f"Cycles run: {len(results)}\n\n")
        for i, (r, p) in enumerate(zip(results, log_paths), 1):
            f.write(f"Cycle {i:03d}: {p.name}\n")
            f.write(f"  errors={len(r['errors'])} warnings={len(r['warnings'])} "
                    f"tracebacks={len(r['tracebacks'])} offline={len(r['offline'])}\n")
            for tb in r["tracebacks"]:
                f.write("  TRACEBACK:\n")
                for line in tb.splitlines():
                    f.write(f"    {line}\n")
            for e in r["errors"][:20]:
                f.write(f"  ERROR: {e[:120]}\n")
    print(f"\n[SUMMARY saved → {summary_path}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--duration", type=int, default=90,
                        help="Seconds to run each cycle before killing")
    parser.add_argument("--pause", type=int, default=3,
                        help="Seconds to pause between cycles")
    args = parser.parse_args()

    all_results = []
    all_paths = []

    for cycle in range(1, args.cycles + 1):
        log_path = run_cycle(cycle, duration=args.duration)
        result = analyse(log_path)
        print_report(cycle, result)
        all_results.append(result)
        all_paths.append(log_path)

        if cycle < args.cycles:
            print(f"  Pausing {args.pause}s before next cycle...")
            time.sleep(args.pause)

    save_summary(all_results, all_paths)

    # Exit non-zero if any cycle had errors
    if any(r["errors"] or r["tracebacks"] for r in all_results):
        sys.exit(1)


if __name__ == "__main__":
    main()
