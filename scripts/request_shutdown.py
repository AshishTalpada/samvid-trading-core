"""Request a graceful shutdown from a detached local Samvid process."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]
PID_PATH = ROOT / "data" / "main.pid"
REQUEST_PATH = ROOT / "data" / "shutdown.request"


def _validated_main_pid() -> int:
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise RuntimeError(f"No valid running PID was found at {PID_PATH}") from exc

    if not psutil.pid_exists(pid):
        raise RuntimeError(f"PID {pid} is not running; remove the stale PID file")

    try:
        command = " ".join(psutil.Process(pid).cmdline()).replace("\\", "/").lower()
    except (psutil.AccessDenied, psutil.NoSuchProcess) as exc:
        raise RuntimeError(f"Unable to validate PID {pid}") from exc
    if "src/main.py" not in command:
        raise RuntimeError(f"PID {pid} is not the Samvid main process")
    return pid


def request_shutdown(timeout: float) -> int:
    pid = _validated_main_pid()
    REQUEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = REQUEST_PATH.with_suffix(f".tmp.{os.getpid()}")
    temporary_path.write_text(str(pid), encoding="utf-8")
    os.replace(temporary_path, REQUEST_PATH)
    print(f"Graceful shutdown requested for PID {pid}.", flush=True)

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not psutil.pid_exists(pid):
            print(f"PID {pid} stopped cleanly.", flush=True)
            return 0
        time.sleep(0.25)
    print(f"PID {pid} did not stop within {timeout:.1f}s.", file=sys.stderr, flush=True)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    try:
        return request_shutdown(args.timeout)
    except RuntimeError as exc:
        print(f"Shutdown request failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
