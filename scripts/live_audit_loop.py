#!/usr/bin/env python3
"""
Live Audit Loop — runs main.py, captures output, summarises errors/warnings.
Usage:
    python scripts/live_audit_loop.py            # run once (90s)
    python scripts/live_audit_loop.py --cycles 5 # run 5 cycles
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _kill_existing_engine() -> None:
    """Kill project engine helpers to prevent duplicate-instance errors."""
    killed: list[int] = []
    own_pid = os.getpid()
    root_marker = str(ROOT).lower()

    # 1. Single PowerShell WMI call — gets all python PIDs + CommandLines atomically.
    #    Much faster and more reliable than per-PID wmic queries.
    try:
        ps_script = (
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" "
            "| Select-Object ProcessId,CommandLine "
            "| ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            pid_str, cmdline = line.split("|", 1)
            try:
                pid = int(pid_str.strip())
            except ValueError:
                continue
            if pid == own_pid:
                continue
            cmdline_lower = cmdline.lower()
            is_project_helper = root_marker in cmdline_lower and (
                "main.py" in cmdline_lower or "watchdog.py" in cmdline_lower
            )
            if is_project_helper and "live_audit_loop" not in cmdline_lower:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True)
                killed.append(pid)
                print(f"  [KILL] Terminated stale project helper PID {pid}")
    except Exception:
        pass

    # 2. Fallback: read PID from .session.bin (sanity-check range to ignore garbage)
    try:
        sentinel = ROOT / ".session.bin"
        if sentinel.exists():
            import struct
            data = sentinel.read_bytes()
            if len(data) >= 4:
                stored_pid = struct.unpack_from("<I", data, 0)[0]
                # Valid OS PIDs on Windows are 4–65536; ignore obviously bogus values
                if 4 <= stored_pid <= 65536 and stored_pid != own_pid and stored_pid not in killed:
                    r2 = subprocess.run(["taskkill", "/F", "/PID", str(stored_pid)],
                                        capture_output=True)
                    if r2.returncode == 0:
                        print(f"  [KILL] Terminated session.bin engine PID {stored_pid}")
    except Exception:
        pass


def _clear_stale_pid_files() -> None:
    """Remove sentinels only when their recorded process is demonstrably dead."""
    for name in ("main.pid", "watchdog.pid"):
        path = ROOT / "data" / name
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            path.unlink(missing_ok=True)


def _run_check(command: list[str], timeout: int = 60) -> dict:
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return {
        "command": command,
        "passed": result.returncode == 0,
        "returncode": result.returncode,
        "duration_sec": round(time.monotonic() - started, 3),
        "output_tail": (result.stdout + result.stderr).splitlines()[-20:],
    }


def run_cycle(cycle: int, duration: int = 90) -> tuple[Path, dict]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"audit_cycle_{cycle:03d}_{ts}.log"

    print(f"\n{'='*70}")
    print(f"CYCLE {cycle:03d} | {datetime.now().strftime('%H:%M:%S')} | log → {log_path.name}")
    print(f"{'='*70}")

    _kill_existing_engine()
    _clear_stale_pid_files()
    time.sleep(2)  # Let ports/sockets release

    cycle_evidence = {
        "cycle": cycle,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "preflight": _run_check([sys.executable, str(ROOT / "scripts" / "startup_validation.py")]),
        "fault_probe": _run_check(
            [
                sys.executable,
                str(ROOT / "src" / "backend_reliability_probe.py"),
                "--json-out",
                str(ROOT / "tmp" / f"audit_cycle_{cycle:03d}_probe.json"),
            ]
        ),
    }

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
            cycle_evidence["timed_out"] = False
        except subprocess.TimeoutExpired:
            print(f"  [{duration}s elapsed] Killing process {proc.pid}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            cycle_evidence["timed_out"] = True

    print(f"  Process ended. Analysing {log_path.name} ...")
    _kill_existing_engine()
    _clear_stale_pid_files()
    cycle_evidence["process_returncode"] = proc.returncode
    cycle_evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    return log_path, cycle_evidence


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

ERROR_RE = re.compile(
    r"(\s-\s(ERROR|CRITICAL)\s-\s|Traceback \(most recent call last\)|^\w+Error:|^\w+Exception:)",
    re.IGNORECASE,
)
WARN_RE  = re.compile(r"\bWARNING\b", re.IGNORECASE)
OFFLINE_RE = re.compile(
    r"(offline|not connected|connection (failed|refused|lost|closed)|"
    r"failed to connect|unable to connect|timed? ?out|"
    r"IBKR.{0,40}not (connected|available|ready|responding)|"
    r"MT5.{0,40}not (connected|available|ready|responding)|"
    r"Dhatu.{0,40}not |OpenBB.{0,40}not |SLM.{0,40}not )",
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


def save_summary(results: list[dict], log_paths: list[Path], evidence: list[dict]) -> Path:
    summary_path = LOG_DIR / f"audit_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    cycles = []
    for result, path, cycle_evidence in zip(results, log_paths, evidence, strict=True):
        cycles.append(
            {
                **cycle_evidence,
                "log_path": path.relative_to(ROOT).as_posix(),
                "analysis": result,
                "passed": (
                    cycle_evidence["preflight"]["passed"]
                    and cycle_evidence["fault_probe"]["passed"]
                    and not result["errors"]
                    and not result["tracebacks"]
                ),
            }
        )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cycles_run": len(cycles),
        "passed": all(cycle["passed"] for cycle in cycles),
        "cycles": cycles,
    }
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n[SUMMARY saved -> {summary_path}]")
    return summary_path


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
    all_evidence = []

    for cycle in range(1, args.cycles + 1):
        log_path, cycle_evidence = run_cycle(cycle, duration=args.duration)
        result = analyse(log_path)
        print_report(cycle, result)
        all_results.append(result)
        all_paths.append(log_path)
        all_evidence.append(cycle_evidence)

        if cycle < args.cycles:
            print(f"  Pausing {args.pause}s before next cycle...")
            time.sleep(args.pause)

    save_summary(all_results, all_paths, all_evidence)

    # Exit non-zero if any cycle had errors or failed its preflight drills.
    if any(r["errors"] or r["tracebacks"] for r in all_results) or any(
        not evidence["preflight"]["passed"] or not evidence["fault_probe"]["passed"]
        for evidence in all_evidence
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
