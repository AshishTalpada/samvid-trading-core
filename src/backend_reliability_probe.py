"""Deterministic backend reliability probe for closed-market validation.

The probe uses synthetic ticks and mocked broker failures. It does not submit
real orders, but it exercises the same safety primitives that protect live
execution: tick batching, order throttling, notional vetoes, DLQ escalation,
and the global trading-state FSM.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from coordinator import TradingCoordinator
from execution_audit import ExecutionAuditLog
from execution_evidence import build_execution_evidence
from intelligence_bus import SharedIntelligenceBus
from resilience_layer import DeadLetterQueue
from risk_invariants import OrderThrottler, RiskInvariants
from tick_batcher import TickBatcher
from trading_state import TradingState, TradingStateManager

logger = logging.getLogger(__name__)


@dataclass
class ProbeCheck:
    name: str
    passed: bool
    details: dict[str, Any]


@dataclass
class ProbeReport:
    passed: bool
    duration_sec: float
    checks: list[ProbeCheck]
    mode: str = "synthetic_closed_market_drill"
    expected_faults: tuple[str, ...] = (
        "ORDER_THROTTLED",
        "NOTIONAL_VETO",
        "ENTRY_DATA_VETO",
        "AUDIT_TAMPER_DETECTED",
        "BROKER_REJECT_DRILL",
        "DLQ_ESCALATION",
        "TradingState.HALTED",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "mode": self.mode,
            "expected_synthetic_faults": list(self.expected_faults),
            "operator_note": (
                "This probe intentionally triggers throttle, notional-veto, data-freshness, "
                "audit-tamper, broker-reject, DLQ, and HALTED paths with mocked data. "
                "These are expected "
                "drill events, not live broker orders."
            ),
            "duration_sec": round(self.duration_sec, 3),
            "checks": [asdict(check) for check in self.checks],
        }


@contextmanager
def _expected_fault_logging(enabled: bool):
    """Optionally silence noisy loggers while a synthetic fault drill is running."""
    if enabled:
        yield
        return

    names = ("risk_invariants", "resilience_layer", "TradingState")
    previous = {name: logging.getLogger(name).disabled for name in names}
    try:
        for name in names:
            logging.getLogger(name).disabled = True
        yield
    finally:
        for name, disabled in previous.items():
            logging.getLogger(name).disabled = disabled


async def _probe_tick_batcher() -> ProbeCheck:
    bus = SharedIntelligenceBus()
    queue = bus.subscribe("tick.batch", maxsize=1000)
    batcher = TickBatcher(flush_interval_ms=5.0, buffer_depth=1000)
    task = asyncio.create_task(batcher.run(bus))

    try:
        price = 500.0
        for i in range(240):
            price -= 0.18 + (i % 7) * 0.01
            spread = 0.02 + (i % 5) * 0.01
            batcher.push("SPY", price, price - spread, price + spread, 100 + i)
            if i % 16 == 0:
                await asyncio.sleep(0)

        await asyncio.sleep(0.05)
        batches: list[dict[str, Any]] = []
        while not queue.empty():
            batches.append(await queue.get())
            queue.task_done()

        total_ticks = sum(int(batch.get("count", 0)) for batch in batches)
        last_price = float(batches[-1]["price"]) if batches else 0.0
        passed = bool(batches) and total_ticks == 240 and last_price < 500.0
        return ProbeCheck(
            "synthetic_tick_batcher",
            passed,
            {
                "batches": len(batches),
                "total_ticks": total_ticks,
                "last_price": round(last_price, 4),
                "batcher_stats": batcher.stats,
            },
        )
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await bus.stop()


async def _probe_order_safety() -> ProbeCheck:
    throttler = OrderThrottler(max_orders=12, per_seconds=60)
    allowed = 0
    blocked = 0
    for _ in range(30):
        if throttler.can_submit():
            allowed += 1
        else:
            blocked += 1

    safe_notional = RiskInvariants.check_notional("SPY", 10, 500.0)
    unsafe_notional = RiskInvariants.check_notional("SPY", 10_000, 500.0)
    passed = allowed == 12 and blocked == 18 and safe_notional and not unsafe_notional
    return ProbeCheck(
        "order_throttle_and_notional_veto",
        passed,
        {
            "allowed": allowed,
            "blocked": blocked,
            "safe_notional": safe_notional,
            "unsafe_notional_blocked": not unsafe_notional,
        },
    )


async def _probe_broker_outage_dlq() -> ProbeCheck:
    TradingStateManager.activate("backend reliability probe start")
    dlq = DeadLetterQueue(max_attempts=2, retry_base_delay=0.01, max_queue_size=10)
    attempts = 0

    async def failing_retry(symbol: str, direction: str, shares: int, price: float) -> bool:
        nonlocal attempts
        attempts += 1
        raise ConnectionError(
            f"synthetic broker outage for {direction} {shares} {symbol} @ {price}"
        )

    worker = asyncio.create_task(dlq.run(failing_retry))
    try:
        dlq.enqueue("QQQ", "BUY", 25, 400.0, reason="synthetic outage")
        await asyncio.wait_for(dlq.join(), timeout=2.0)
        stats = dlq.stats
        passed = (
            attempts == 2
            and stats["escalations"] == 1
            and TradingStateManager.state() == TradingState.HALTED
        )
        return ProbeCheck(
            "dead_letter_queue_escalates_to_halt",
            passed,
            {
                "attempts": attempts,
                "dlq_stats": stats,
                "trading_state": TradingStateManager.status_str(),
            },
        )
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        TradingStateManager.activate("backend reliability probe complete")


async def _probe_entry_data_freshness() -> ProbeCheck:
    brain = SimpleNamespace(mode="ibkr_paper", _last_fresh_bar_at={})
    coordinator = TradingCoordinator(SimpleNamespace(), brain)
    missing_reason = coordinator._entry_data_block_reason("SPY")

    brain._last_fresh_bar_at["SPY"] = time.monotonic() - 120.0
    expired_reason = coordinator._entry_data_block_reason("SPY")

    brain._last_fresh_bar_at["SPY"] = time.monotonic()
    fresh_reason = coordinator._entry_data_block_reason("SPY")

    passed = (
        missing_reason == "no verified fresh bar available"
        and bool(expired_reason and "expired" in expired_reason)
        and fresh_reason is None
    )
    return ProbeCheck(
        "entry_data_freshness_veto",
        passed,
        {
            "missing_proof_blocked": missing_reason is not None,
            "expired_proof_blocked": expired_reason is not None,
            "fresh_proof_allowed": fresh_reason is None,
        },
    )


async def _probe_execution_audit_chain() -> ProbeCheck:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "execution_audit.jsonl"
        audit = ExecutionAuditLog(path)
        audit.append(
            event="ORDER_INTENT",
            symbol="SPY",
            side="BUY",
            quantity=1,
            order_type="LMT",
            details={"price": 500.0},
        )
        audit.append(
            event="ORDER_INTENT",
            symbol="QQQ",
            side="SELL",
            quantity=2,
            order_type="LMT",
            details={"price": 400.0},
        )
        clean_verification = audit.verify()

        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        records[0]["quantity"] = 999.0
        path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        tampered_verification = audit.verify()
        passed = clean_verification["valid"] and not tampered_verification["valid"]
        return ProbeCheck(
            "execution_audit_tamper_detection",
            passed,
            {
                "clean_chain_valid": clean_verification["valid"],
                "tampered_chain_blocked": not tampered_verification["valid"],
            },
        )


async def _probe_execution_lifecycle_evidence() -> ProbeCheck:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "execution_audit.jsonl"
        audit = ExecutionAuditLog(path)
        intent_id = "synthetic-lifecycle-intent"
        audit.append(
            event="ORDER_INTENT",
            symbol="SPY",
            side="BUY",
            quantity=2,
            order_type="SINGLE",
            intent_id=intent_id,
            details={"px": 500.0},
        )
        audit.append(
            event="ORDER_FILL",
            symbol="SPY",
            side="BOT",
            quantity=2,
            order_type="FILL",
            intent_id=intent_id,
            details={"fill_price": 500.25, "lineage_status": "MATCHED"},
        )
        audit.append(
            event="ORDER_COMMISSION",
            symbol="SPY",
            side="BOT",
            quantity=2,
            order_type="COMMISSION",
            intent_id=intent_id,
            details={"commission": 1.25, "lineage_status": "MATCHED"},
        )
        audit.append(
            event="ORDER_CANCEL_REQUEST",
            symbol="SPY",
            side="SELL",
            quantity=2,
            order_type="LMT",
            intent_id=intent_id,
            details={"lineage_status": "MATCHED"},
        )
        audit.append(
            event="ORDER_STATUS",
            symbol="SPY",
            side="SELL",
            quantity=2,
            order_type="LMT",
            intent_id=intent_id,
            details={"status": "Inactive", "lineage_status": "MATCHED"},
        )
        audit.append(
            event="BROKER_ERROR",
            symbol="SPY",
            side="SELL",
            quantity=2,
            order_type="ERROR",
            intent_id=intent_id,
            details={"error_code": 201, "severity": "CRITICAL", "lineage_status": "MATCHED"},
        )
        evidence = build_execution_evidence(path)
        passed = (
            evidence["lineage"]["intent_fill_rate"] == 1.0
            and evidence["lineage"]["unmatched_lineage_events"] == 0
            and evidence["costs"]["total_commission"] == 1.25
            and evidence["costs"]["total_observed_slippage"] == 0.5
            and evidence["routing"]["terminal_statuses"] == {"Inactive": 1}
            and evidence["routing"]["broker_errors"] == 1
        )
        return ProbeCheck(
            "execution_lifecycle_evidence",
            passed,
            evidence,
        )


async def run_backend_reliability_probe(*, verbose_expected_faults: bool = False) -> ProbeReport:
    started = time.monotonic()
    checks = [
        await _probe_tick_batcher(),
        await _probe_entry_data_freshness(),
        await _probe_execution_audit_chain(),
        await _probe_execution_lifecycle_evidence(),
    ]
    with _expected_fault_logging(verbose_expected_faults):
        checks.append(await _probe_order_safety())
        checks.append(await _probe_broker_outage_dlq())
    return ProbeReport(
        passed=all(check.passed for check in checks),
        duration_sec=time.monotonic() - started,
        checks=checks,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run synthetic backend reliability probes.")
    parser.add_argument(
        "--json-out",
        default="data/backend_reliability_probe.json",
        help="Path to write the probe report JSON.",
    )
    parser.add_argument(
        "--verbose-expected-faults",
        action="store_true",
        help="Print the intentionally-triggered throttle/veto/DLQ fault logs.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    report = asyncio.run(
        run_backend_reliability_probe(verbose_expected_faults=args.verbose_expected_faults)
    )
    payload = report.to_dict()
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
