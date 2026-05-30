"""Deterministic execution-quality evidence from the tamper-evident audit log."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from execution_audit import ExecutionAuditLog


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _read_verified_records(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    verification = ExecutionAuditLog(path).verify()
    if not verification["valid"]:
        raise ValueError(f"execution audit verification failed: {verification['error']}")
    if not path.exists():
        return [], verification
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return records, verification


def build_execution_evidence(
    path: str | Path = "data/execution_audit.jsonl",
    *,
    since_timestamp_ns: int = 0,
) -> dict[str, Any]:
    """Summarize verifiable execution quality for one audit-log window."""
    records, verification = _read_verified_records(Path(path))
    records = [
        record
        for record in records
        if int(record.get("timestamp_ns", 0)) >= int(since_timestamp_ns)
    ]
    event_counts = Counter(str(record.get("event", "UNKNOWN")) for record in records)
    intents = {
        str(record["intent_id"]): record
        for record in records
        if record.get("event") == "ORDER_INTENT" and record.get("intent_id")
    }
    first_fill_by_intent: dict[str, dict[str, Any]] = {}
    matched_fills = 0
    unmatched_lineage_events = 0
    slippage_values: list[float] = []
    commissions: list[float] = []

    for record in records:
        details = record.get("details") or {}
        intent_id = str(record.get("intent_id", ""))
        if record.get("event") != "ORDER_INTENT" and details.get("lineage_status") == "UNMATCHED":
            unmatched_lineage_events += 1
        if record.get("event") == "ORDER_FILL":
            if details.get("lineage_status") == "MATCHED" and intent_id in intents:
                matched_fills += 1
                first_fill_by_intent.setdefault(intent_id, record)
                intent_price = float((intents[intent_id].get("details") or {}).get("px", 0) or 0)
                fill_price = float(details.get("fill_price", 0) or 0)
                quantity = float(record.get("quantity", 0) or 0)
                if intent_price > 0 and fill_price > 0 and quantity > 0:
                    slippage_values.append(abs(fill_price - intent_price) * quantity)
        if record.get("event") == "ORDER_COMMISSION":
            commissions.append(float(details.get("commission", 0) or 0))

    fill_latencies_ms = [
        (int(fill["timestamp_ns"]) - int(intents[intent_id]["timestamp_ns"])) / 1_000_000
        for intent_id, fill in first_fill_by_intent.items()
        if int(fill["timestamp_ns"]) >= int(intents[intent_id]["timestamp_ns"])
    ]
    intent_count = len(intents)
    filled_intents = len(first_fill_by_intent)
    legacy_records = sum(1 for record in records if not record.get("intent_id"))
    cancel_statuses = Counter(
        str((record.get("details") or {}).get("status", "UNKNOWN"))
        for record in records
        if record.get("event") == "ORDER_STATUS"
    )

    return {
        "audit": {
            "valid": verification["valid"],
            "records_checked": verification["records_checked"],
            "window_records": len(records),
        },
        "lineage": {
            "intents": intent_count,
            "filled_intents": filled_intents,
            "unfilled_intents": max(0, intent_count - filled_intents),
            "matched_fills": matched_fills,
            "unmatched_lineage_events": unmatched_lineage_events,
            "legacy_records_without_intent_id": legacy_records,
            "intent_fill_rate": filled_intents / intent_count if intent_count else 0.0,
        },
        "routing": {
            "event_counts": dict(sorted(event_counts.items())),
            "terminal_statuses": dict(sorted(cancel_statuses.items())),
            "broker_errors": event_counts["BROKER_ERROR"],
        },
        "costs": {
            "commission_reports": len(commissions),
            "total_commission": sum(commissions),
            "observed_slippage_events": len(slippage_values),
            "total_observed_slippage": sum(slippage_values),
        },
        "latency_ms": {
            "samples": len(fill_latencies_ms),
            "mean": statistics.fmean(fill_latencies_ms) if fill_latencies_ms else 0.0,
            "p50": _percentile(fill_latencies_ms, 0.50),
            "p95": _percentile(fill_latencies_ms, 0.95),
            "max": max(fill_latencies_ms, default=0.0),
        },
    }
