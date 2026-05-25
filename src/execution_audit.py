"""Append-only execution audit utilities."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


class ExecutionAuditLog:
    """Tamper-evident JSONL audit log for order routing events."""

    def __init__(self, path: str | os.PathLike[str] = "data/execution_audit.jsonl") -> None:
        self.path = Path(path)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        try:
            with self.path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                pos = handle.tell()
                if pos == 0:
                    return "GENESIS"
                buf = bytearray()
                pos -= 1
                while pos >= 0:
                    handle.seek(pos)
                    char = handle.read(1)
                    if char == b"\n" and buf:
                        break
                    buf.extend(char)
                    pos -= 1
            line = bytes(reversed(buf)).decode("utf-8", errors="replace").strip()
            if not line:
                return "GENESIS"
            return str(json.loads(line).get("hash", "GENESIS"))
        except Exception:
            return "CORRUPT_PREVIOUS"

    @staticmethod
    def _hash_record(record: dict[str, Any]) -> str:
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def append(
        self,
        *,
        event: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_hash = self._last_hash()
        record = {
            "timestamp_ns": time.time_ns(),
            "event": event,
            "symbol": str(symbol).upper(),
            "side": str(side).upper(),
            "quantity": float(quantity),
            "order_type": str(order_type).upper(),
            "details": details or {},
            "previous_hash": previous_hash,
        }
        record["hash"] = self._hash_record(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return record
