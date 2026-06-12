"""Deterministic execution-quality evidence from the tamper-evident audit log."""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from execution_audit import ExecutionAuditLog


def _normalized_side(side: str) -> str:
    value = str(side).upper()
    if value in {"BUY", "BOT"}:
        return "BUY"
    if value in {"SELL", "SLD"}:
        return "SELL"
    return value


def _weighted_fill(fills: list[dict[str, Any]]) -> tuple[float, float]:
    quantity = sum(abs(float(record.get("quantity", 0) or 0)) for record in fills)
    notional = sum(
        abs(float(record.get("quantity", 0) or 0))
        * float((record.get("details") or {}).get("fill_price", 0) or 0)
        for record in fills
    )
    return quantity, notional / quantity if quantity > 0 else 0.0


def _completed_bracket_economics(
    records: list[dict[str, Any]], intent: dict[str, Any]
) -> dict[str, float] | None:
    intent_id = str(intent.get("intent_id", ""))
    intended_qty = abs(float(intent.get("quantity", 0) or 0))
    entry_side = _normalized_side(str(intent.get("side", "")))
    if not intent_id or intended_qty <= 0 or entry_side not in {"BUY", "SELL"}:
        return None

    lineage = [record for record in records if str(record.get("intent_id", "")) == intent_id]
    fills = [
        record
        for record in lineage
        if record.get("event") == "ORDER_FILL"
        and (record.get("details") or {}).get("lineage_status") == "MATCHED"
    ]
    entry_fills = [record for record in fills if _normalized_side(record.get("side", "")) == entry_side]
    exit_fills = [record for record in fills if _normalized_side(record.get("side", "")) != entry_side]
    entry_qty, entry_price = _weighted_fill(entry_fills)
    exit_qty, exit_price = _weighted_fill(exit_fills)
    if (
        entry_price <= 0
        or exit_price <= 0
        or not math.isclose(entry_qty, intended_qty, abs_tol=0.1)
        or not math.isclose(exit_qty, intended_qty, abs_tol=0.1)
    ):
        return None

    commissions = [record for record in lineage if record.get("event") == "ORDER_COMMISSION"]
    entry_commission = sum(
        float((record.get("details") or {}).get("commission", 0) or 0)
        for record in commissions
        if _normalized_side(record.get("side", "")) == entry_side
    )
    exit_commission = sum(
        float((record.get("details") or {}).get("commission", 0) or 0)
        for record in commissions
        if _normalized_side(record.get("side", "")) != entry_side
    )
    first_entry_ns = min(int(record.get("timestamp_ns", 0) or 0) for record in entry_fills)
    last_exit_ns = max(int(record.get("timestamp_ns", 0) or 0) for record in exit_fills)
    return {
        "quantity": intended_qty,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "entry_commission": entry_commission,
        "exit_commission": exit_commission,
        "hold_hours": max(0.0, (last_exit_ns - first_entry_ns) / 3_600_000_000_000),
    }


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
    fill_qty_by_intent: dict[str, float] = {}
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
                fill_qty_by_intent[intent_id] = fill_qty_by_intent.get(intent_id, 0.0) + quantity
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
    overfilled_intents = 0
    underfilled_intents = 0
    for intent_id, intent_record in intents.items():
        intended_qty = abs(float(intent_record.get("quantity", 0) or 0))
        filled_qty = abs(fill_qty_by_intent.get(intent_id, 0.0))
        if intended_qty <= 0 or filled_qty <= 0:
            continue
        if filled_qty > intended_qty * 1.001:
            overfilled_intents += 1
        elif filled_qty < intended_qty * 0.999:
            underfilled_intents += 1
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
            "fill_fragments": max(0, matched_fills - filled_intents),
            "overfilled_intents": overfilled_intents,
            "underfilled_intents": underfilled_intents,
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


def repair_trade_ledger_from_execution_audit(
    conn: sqlite3.Connection,
    path: str | Path = "data/execution_audit.jsonl",
    *,
    outcomes: tuple[str, ...] = ("RECONCILIATION_REQUIRED",),
    apply: bool = True,
) -> list[dict[str, Any]]:
    """Repair uniquely matched trade rows from complete, hash-verified broker fills."""
    records, _verification = _read_verified_records(Path(path))
    if not records or not outcomes:
        return []

    intents = [
        record
        for record in records
        if record.get("event") == "ORDER_INTENT"
        and record.get("order_type") == "BRACKET"
        and record.get("intent_id")
    ]
    placeholders = ",".join("?" for _ in outcomes)
    rows = conn.execute(
        "SELECT id, timestamp, instrument, direction, entry_price, stop_price, outcome, notes "
        f"FROM trades WHERE outcome IN ({placeholders})",
        outcomes,
    ).fetchall()
    columns = (
        "id",
        "timestamp",
        "instrument",
        "direction",
        "entry_price",
        "stop_price",
        "outcome",
        "notes",
    )
    repairs: list[dict[str, Any]] = []

    for raw_row in rows:
        row = dict(zip(columns, raw_row, strict=True))
        if "AUDIT_RECONCILED" in str(row.get("notes") or ""):
            continue
        try:
            trade_ts = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
            if trade_ts.tzinfo is None:
                trade_ts = trade_ts.replace(tzinfo=timezone.utc)
            trade_epoch = trade_ts.timestamp()
            intended_price = float(row["entry_price"] or 0)
        except (TypeError, ValueError):
            continue

        expected_side = "BUY" if str(row["direction"]).upper() == "LONG" else "SELL"
        candidates = []
        for intent in intents:
            details = intent.get("details") or {}
            intent_price = float(details.get("px", 0) or 0)
            intent_epoch = int(intent.get("timestamp_ns", 0) or 0) / 1_000_000_000
            if (
                intent.get("symbol") == row["instrument"]
                and _normalized_side(intent.get("side", "")) == expected_side
                and math.isclose(intent_price, intended_price, abs_tol=0.000001)
                and abs(intent_epoch - trade_epoch) <= 300
            ):
                candidates.append(intent)
        if len(candidates) != 1:
            continue

        intent = candidates[0]
        economics = _completed_bracket_economics(records, intent)
        if economics is None:
            continue
        signed_qty = economics["quantity"] if expected_side == "BUY" else -economics["quantity"]
        gross_pnl = (economics["exit_price"] - economics["entry_price"]) * signed_qty
        total_commission = economics["entry_commission"] + economics["exit_commission"]
        net_pnl = gross_pnl - total_commission
        stop_price = float(row["stop_price"] or 0)
        risk_per_share = abs(economics["entry_price"] - stop_price)
        direction_sign = 1.0 if signed_qty > 0 else -1.0
        r_multiple = (
            ((economics["exit_price"] - economics["entry_price"]) / risk_per_share)
            * direction_sign
            if risk_per_share > 0
            else 0.0
        )
        intended_price = float((intent.get("details") or {}).get("px", 0) or 0)
        adverse_slippage = (
            max(economics["entry_price"] - intended_price, 0.0) * economics["quantity"]
            if signed_qty > 0
            else max(intended_price - economics["entry_price"], 0.0) * economics["quantity"]
        )
        outcome = "WIN" if net_pnl > 0 else "LOSS" if net_pnl < 0 else "BREAKEVEN"
        repair = {
            "trade_id": int(row["id"]),
            "symbol": str(row["instrument"]),
            "intent_id": str(intent["intent_id"]),
            "entry_price": economics["entry_price"],
            "exit_price": economics["exit_price"],
            "quantity": economics["quantity"],
            "gross_pnl": gross_pnl,
            "net_pnl": net_pnl,
            "r_multiple": r_multiple,
            "entry_commission": economics["entry_commission"],
            "exit_commission": economics["exit_commission"],
            "slippage": adverse_slippage,
            "hold_hours": economics["hold_hours"],
            "outcome": outcome,
        }
        repairs.append(repair)
        if apply:
            conn.execute(
                "UPDATE trades SET entry_price=?, exit_price=?, shares=?, outcome=?, "
                "pnl_dollars=?, net_pnl=?, r_multiple=?, hold_hours=?, commission=?, "
                "slippage=?, notes=COALESCE(notes || ' | ', '') || ? WHERE id=?",
                (
                    repair["entry_price"],
                    repair["exit_price"],
                    repair["quantity"],
                    repair["outcome"],
                    repair["gross_pnl"],
                    repair["net_pnl"],
                    repair["r_multiple"],
                    repair["hold_hours"],
                    repair["entry_commission"],
                    repair["slippage"],
                    f"AUDIT_RECONCILED intent_id={repair['intent_id']} "
                    f"exit_commission={repair['exit_commission']:.6f}",
                    repair["trade_id"],
                ),
            )

    if apply and repairs:
        summary_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='performance_summary'"
        ).fetchone()
        if summary_table:
            summary_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(performance_summary)").fetchall()
            }
            if {"key", "value"}.issubset(summary_columns):
                aggregate = conn.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END), "
                    "SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END), SUM(net_pnl), "
                    "AVG(r_multiple) FROM trades "
                    "WHERE outcome IN ('WIN','LOSS','BREAKEVEN') AND net_pnl IS NOT NULL"
                ).fetchone()
                closed_count = int(aggregate[0] or 0)
                wins = int(aggregate[1] or 0)
                losses = int(aggregate[2] or 0)
                summary = {
                    "closed_count": closed_count,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": wins / closed_count if closed_count else 0.0,
                    "net_pnl": float(aggregate[3] or 0.0),
                    "avg_r": float(aggregate[4] or 0.0),
                    "updated_from": "execution_audit_reconciliation",
                }
                conn.execute(
                    "INSERT OR REPLACE INTO performance_summary (key, value, updated_at) "
                    "VALUES ('latest', ?, ?)",
                    (json.dumps(summary), datetime.now(timezone.utc).isoformat()),
                )
        conn.commit()
    return repairs
