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
            record = json.loads(line)
            record_hash = record.get("hash")
            if not record_hash:
                raise ValueError("execution audit tail is missing hash")
            return str(record_hash)
        except Exception as exc:
            raise ValueError(f"execution audit tail is corrupt: {exc}") from exc

    @staticmethod
    def _hash_record(record: dict[str, Any]) -> str:
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def verify(self) -> dict[str, Any]:
        """Verify every hash and link in the JSONL chain."""
        if not self.path.exists():
            return {"valid": True, "records_checked": 0, "last_hash": "GENESIS"}

        expected_previous = "GENESIS"
        records_checked = 0
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    if not raw_line.strip():
                        continue
                    record = json.loads(raw_line)
                    stored_hash = str(record.pop("hash"))
                    if record.get("previous_hash") != expected_previous:
                        raise ValueError(f"line {line_number}: previous hash mismatch")
                    computed_hash = self._hash_record(record)
                    if stored_hash != computed_hash:
                        raise ValueError(f"line {line_number}: record hash mismatch")
                    expected_previous = stored_hash
                    records_checked += 1
        except Exception as exc:
            return {
                "valid": False,
                "records_checked": records_checked,
                "last_hash": expected_previous,
                "error": str(exc),
            }
        return {
            "valid": True,
            "records_checked": records_checked,
            "last_hash": expected_previous,
        }

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
