"""Run a deterministic active-hours synthetic market soak against backend primitives."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import asyncio
import json
import logging
import math
import random
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agent_c_ibkr import BlackSwanProtocol
from brain_data import DataProvider
from data_pipeline import DataPipeline
from execution_audit import ExecutionAuditLog
from execution_evidence import build_execution_evidence
from intelligence_bus import SharedIntelligenceBus
from risk_invariants import OrderThrottler, RiskInvariants
from tick_batcher import TickBatcher

logger = logging.getLogger("active_hours_soak")

BASE_PRICES = {
    "SPY": 525.0,
    "QQQ": 455.0,
    "IWM": 210.0,
    "DIA": 395.0,
    "AAPL": 195.0,
    "MSFT": 425.0,
    "GOOGL": 175.0,
    "AMZN": 185.0,
    "NVDA": 125.0,
    "META": 505.0,
    "TSLA": 245.0,
    "AMD": 165.0,
    "AVGO": 172.0,
    "SMCI": 45.0,
    "ARM": 135.0,
    "MU": 115.0,
    "PLTR": 28.0,
    "COIN": 245.0,
    "MSTR": 1650.0,
    "JPM": 205.0,
    "GS": 465.0,
    "V": 280.0,
    "MA": 475.0,
    "WMT": 68.0,
    "COST": 850.0,
    "NFLX": 650.0,
}


@dataclass
class SyntheticPosition:
    symbol: str
    side: str
    quantity: int
    entry_price: float
    stop_price: float
    target_price: float
    opened_at: float
    intent_id: str


@dataclass
class SoakStats:
    ticks_published: int = 0
    tick_events_consumed: int = 0
    batches_consumed: int = 0
    batch_ticks_consumed: int = 0
    cache_checks: int = 0
    cache_failures: int = 0
    signals_considered: int = 0
    signals_frozen: int = 0
    signals_throttled: int = 0
    signals_notional_vetoed: int = 0
    entries_filled: int = 0
    exits_filled: int = 0
    wins: int = 0
    losses: int = 0
    realized_net_pnl: float = 0.0
    max_open_positions: int = 0
    max_drawdown_pct: float = 0.0
    forced_flatten_exits: int = 0


class ActiveHoursSyntheticMarket:
    """Correlated active-session tape with deterministic regime and spread changes."""

    def __init__(self, seed: int = 20260531) -> None:
        self.rng = random.Random(seed)
        self.prices = dict(BASE_PRICES)
        self.anchors = dict(BASE_PRICES)
        self.history = {symbol: deque([price], maxlen=64) for symbol, price in self.prices.items()}

    @staticmethod
    def regime(progress: float) -> tuple[str, float, float, float]:
        """Return regime, VIX, drift-bps, and volatility-bps for the virtual session."""
        if progress < 0.30:
            return "TREND_UP", 17.0, 0.10, 1.5
        if progress < 0.55:
            return "CHOPPY", 22.0, 0.0, 2.2
        if progress < 0.72:
            return "VOLATILE", 65.0, -0.18, 5.5
        return "RECOVERY", 24.0, 0.06, 2.4

    def step(self, progress: float, tick_hz: float) -> tuple[str, float, list[dict[str, Any]]]:
        regime, vix, drift_bps, vol_bps = self.regime(progress)
        intraday_u_shape = 0.75 + 1.1 * abs(progress - 0.5)
        scale = 1.0 / math.sqrt(max(tick_hz, 1.0))
        market_factor = self.rng.gauss(drift_bps, vol_bps * intraday_u_shape) * scale
        quotes = []
        for index, symbol in enumerate(DataProvider.EXECUTION_WATCHLIST):
            price = self.prices[symbol]
            beta = 0.75 + (index % 7) * 0.10
            idio = self.rng.gauss(0.0, vol_bps * 0.55) * scale
            anchor_pull = ((self.anchors[symbol] - price) / self.anchors[symbol]) * 0.8
            jump = 0.0
            if regime == "VOLATILE" and self.rng.random() < 0.0015:
                jump = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(8.0, 22.0)
            next_price = max(
                0.01,
                price * (1.0 + (beta * market_factor + idio + jump + anchor_pull) / 10_000),
            )
            spread_bps = max(0.4, 0.8 + vol_bps * 0.28 + abs(idio) * 0.12)
            half_spread = next_price * spread_bps / 20_000
            size = max(1, int(self.rng.lognormvariate(4.7, 0.7)))
            self.prices[symbol] = next_price
            self.history[symbol].append(next_price)
            quotes.append(
                {
                    "symbol": symbol,
                    "price": next_price,
                    "bid": next_price - half_spread,
                    "ask": next_price + half_spread,
                    "size": size,
                    "source": "SyntheticActiveHours",
                    "ts": time.time_ns(),
                }
            )
        return regime, vix, quotes

    def momentum(self, symbol: str) -> float:
        prices = self.history[symbol]
        if len(prices) < 16:
            return 0.0
        return prices[-1] / prices[-16] - 1.0


def _pipeline_cache() -> DataPipeline:
    pipeline = DataPipeline.__new__(DataPipeline)
    pipeline._price_cache = {}
    pipeline._price_cache_ts = {}
    pipeline._price_cache_source = {}
    return pipeline


def _record_fill(
    audit: ExecutionAuditLog,
    *,
    intent_id: str,
    symbol: str,
    side: str,
    quantity: int,
    intended_price: float,
    fill_price: float,
    commission: float,
) -> None:
    audit.append(
        event="ORDER_FILL",
        symbol=symbol,
        side="BOT" if side == "BUY" else "SLD",
        quantity=quantity,
        order_type="FILL",
        intent_id=intent_id,
        details={"fill_price": fill_price, "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_COMMISSION",
        symbol=symbol,
        side="BOT" if side == "BUY" else "SLD",
        quantity=quantity,
        order_type="COMMISSION",
        intent_id=intent_id,
        details={"commission": commission, "currency": "USD", "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_STATUS",
        symbol=symbol,
        side=side,
        quantity=quantity,
        order_type="MKT",
        intent_id=intent_id,
        details={
            "status": "Filled",
            "lineage_status": "MATCHED",
            "intended_price": intended_price,
        },
    )


async def run_active_hours_soak(
    *,
    duration_sec: float = 1200.0,
    tick_hz: float = 4.0,
    report_sec: float = 60.0,
    signal_interval_sec: float = 12.0,
    max_hold_sec: float = 90.0,
    seed: int = 20260531,
    json_out: str | Path = "tmp/active_hours_soak_latest.json",
) -> dict[str, Any]:
    """Run the backend soak and return a machine-readable synthetic evidence report."""
    started = time.monotonic()
    out_path = ROOT / Path(json_out)
    audit_path = out_path.with_name(f"{out_path.stem}_execution_audit.jsonl")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.unlink(missing_ok=True)
    audit = ExecutionAuditLog(audit_path)
    bus = SharedIntelligenceBus()
    tick_queue = bus.subscribe("tick.hft", maxsize=10_000)
    batch_queue = bus.subscribe("tick.batch", maxsize=10_000)
    batcher = TickBatcher(flush_interval_ms=5.0, buffer_depth=10_000)
    batcher_task = asyncio.create_task(batcher.run(bus))
    pipeline = _pipeline_cache()
    market = ActiveHoursSyntheticMarket(seed=seed)
    throttler = OrderThrottler(max_orders=24, per_seconds=60)
    black_swan = BlackSwanProtocol()
    stats = SoakStats()
    positions: dict[str, SyntheticPosition] = {}
    trade_sequence = 0
    equity = 100_000.0
    peak_equity = equity
    last_signal_at = started - 30.0
    last_report_at = started
    next_tick_at = started

    def close_position(
        symbol: str,
        position: SyntheticPosition,
        *,
        price: float,
        regime: str,
        reason: str,
    ) -> None:
        nonlocal equity, peak_equity, trade_sequence
        exit_side = "SELL" if position.side == "BUY" else "BUY"
        side_sign = 1 if position.side == "BUY" else -1
        spread = max(0.01, price * 0.00012)
        fill_price = price - spread / 2 if exit_side == "SELL" else price + spread / 2
        commission = max(1.0, position.quantity * 0.005)
        trade_sequence += 1
        intent_id = f"soak-exit-{trade_sequence}"
        audit.append(
            event="ORDER_INTENT",
            symbol=symbol,
            side=exit_side,
            quantity=position.quantity,
            order_type="MKT",
            intent_id=intent_id,
            details={"px": price, "regime": regime, "reason": reason, "synthetic": True},
        )
        _record_fill(
            audit,
            intent_id=intent_id,
            symbol=symbol,
            side=exit_side,
            quantity=position.quantity,
            intended_price=price,
            fill_price=fill_price,
            commission=commission,
        )
        pnl = (fill_price - position.entry_price) * position.quantity * side_sign - commission
        stats.realized_net_pnl += pnl
        equity += pnl
        peak_equity = max(peak_equity, equity)
        stats.max_drawdown_pct = max(
            stats.max_drawdown_pct, (peak_equity - equity) / max(peak_equity, 1.0)
        )
        stats.exits_filled += 1
        stats.wins += int(pnl > 0)
        stats.losses += int(pnl <= 0)
        stats.forced_flatten_exits += int(reason == "SESSION_END")
        del positions[symbol]

    async def consume_ticks() -> None:
        while True:
            await tick_queue.get()
            stats.tick_events_consumed += 1
            tick_queue.task_done()

    async def consume_batches() -> None:
        while True:
            batch = await batch_queue.get()
            stats.batches_consumed += 1
            stats.batch_ticks_consumed += int(batch.get("count", 0) or 0)
            batch_queue.task_done()

    consumers = [asyncio.create_task(consume_ticks()), asyncio.create_task(consume_batches())]
    try:
        while True:
            now = time.monotonic()
            elapsed = now - started
            if elapsed >= duration_sec:
                break
            progress = min(1.0, elapsed / max(duration_sec, 0.001))
            regime, vix, quotes = market.step(progress, tick_hz)
            for quote in quotes:
                pipeline.record_realtime_tick(quote)
                batcher.push(
                    quote["symbol"], quote["price"], quote["bid"], quote["ask"], quote["size"]
                )
                await bus.publish("tick.hft", quote)
                stats.ticks_published += 1
                if pipeline._fresh_realtime_price(quote["symbol"]) != quote["price"]:
                    stats.cache_failures += 1
                stats.cache_checks += 1

            for symbol, position in list(positions.items()):
                price = market.prices[symbol]
                age = now - position.opened_at
                side_sign = 1 if position.side == "BUY" else -1
                stop_hit = price <= position.stop_price if side_sign > 0 else price >= position.stop_price
                target_hit = (
                    price >= position.target_price if side_sign > 0 else price <= position.target_price
                )
                if not (stop_hit or target_hit or age >= max_hold_sec):
                    continue
                reason = "STOP" if stop_hit else "TARGET" if target_hit else "MAX_HOLD"
                close_position(symbol, position, price=price, regime=regime, reason=reason)

            if now - last_signal_at >= signal_interval_sec and len(positions) < 6:
                stats.signals_considered += 1
                drawdown = (peak_equity - equity) / max(peak_equity, 1.0)
                if black_swan.check(vix=vix, drawdown_pct=drawdown) == "FREEZE":
                    stats.signals_frozen += 1
                elif not throttler.can_submit():
                    stats.signals_throttled += 1
                else:
                    symbol = max(
                        (item for item in DataProvider.EXECUTION_WATCHLIST if item not in positions),
                        key=lambda item: abs(market.momentum(item)),
                    )
                    price = market.prices[symbol]
                    quantity = max(1, int(5_000 / price))
                    if not RiskInvariants.check_notional(symbol, quantity, price):
                        stats.signals_notional_vetoed += 1
                    else:
                        side = "BUY" if market.momentum(symbol) >= 0 else "SELL"
                        spread = max(0.01, price * 0.00012)
                        fill_price = price + spread / 2 if side == "BUY" else price - spread / 2
                        commission = max(1.0, quantity * 0.005)
                        trade_sequence += 1
                        intent_id = f"soak-entry-{trade_sequence}"
                        audit.append(
                            event="ORDER_INTENT",
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            order_type="MKT",
                            intent_id=intent_id,
                            details={"px": price, "regime": regime, "synthetic": True},
                        )
                        _record_fill(
                            audit,
                            intent_id=intent_id,
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            intended_price=price,
                            fill_price=fill_price,
                            commission=commission,
                        )
                        side_sign = 1 if side == "BUY" else -1
                        positions[symbol] = SyntheticPosition(
                            symbol=symbol,
                            side=side,
                            quantity=quantity,
                            entry_price=fill_price,
                            stop_price=fill_price * (1.0 - side_sign * 0.005),
                            target_price=fill_price * (1.0 + side_sign * 0.0075),
                            opened_at=now,
                            intent_id=intent_id,
                        )
                        stats.entries_filled += 1
                        stats.max_open_positions = max(stats.max_open_positions, len(positions))
                last_signal_at = now

            if now - last_report_at >= report_sec:
                logger.info(
                    "SOAK %.0fs/%ss regime=%s vix=%.1f ticks=%s entries=%s exits=%s "
                    "open=%s pnl=$%.2f cache_failures=%s",
                    elapsed,
                    round(duration_sec),
                    regime,
                    vix,
                    stats.ticks_published,
                    stats.entries_filled,
                    stats.exits_filled,
                    len(positions),
                    stats.realized_net_pnl,
                    stats.cache_failures,
                )
                last_report_at = now

            next_tick_at += 1.0 / max(tick_hz, 1.0)
            await asyncio.sleep(max(0.0, next_tick_at - time.monotonic()))

        final_regime, _, _, _ = market.regime(1.0)
        for symbol, position in list(positions.items()):
            close_position(
                symbol,
                position,
                price=market.prices[symbol],
                regime=final_regime,
                reason="SESSION_END",
            )

        stale_probe = _pipeline_cache()
        stale_probe.record_realtime_tick(
            {"symbol": "SPY", "price": 525.0, "source": "SyntheticActiveHours"}
        )
        stale_probe._price_cache_ts["SPY"] = time.monotonic() - 60.0
        stale_cache_rejected = stale_probe._fresh_realtime_price("SPY") is None
        await asyncio.sleep(0.05)
        await asyncio.wait_for(tick_queue.join(), timeout=2.0)
        await asyncio.wait_for(batch_queue.join(), timeout=2.0)
        evidence = build_execution_evidence(audit_path)
        stats_payload = asdict(stats)
        checks = {
            "ticks_fully_consumed": stats.tick_events_consumed == stats.ticks_published,
            "batcher_no_drops": batcher.stats["drop_count"] == 0,
            "realtime_cache_no_failures": stats.cache_failures == 0,
            "stale_realtime_cache_rejected": stale_cache_rejected,
            "execution_audit_valid": evidence["audit"]["valid"],
            "execution_lineage_complete": evidence["lineage"]["intent_fill_rate"] == 1.0,
            "execution_lineage_matched": evidence["lineage"]["unmatched_lineage_events"] == 0,
            "risk_freeze_exercised": stats.signals_frozen > 0,
            "orders_exercised": stats.entries_filled > 0 and stats.exits_filled > 0,
            "positions_flattened_at_end": not positions,
        }
        report = {
            "mode": "synthetic_active_hours_soak",
            "promotion_eligible": False,
            "operator_note": (
                "Synthetic soak verifies backend reliability and execution evidence plumbing only. "
                "It does not prove strategy alpha or authorize live promotion."
            ),
            "duration_sec": round(time.monotonic() - started, 3),
            "seed": seed,
            "tick_hz": tick_hz,
            "signal_interval_sec": signal_interval_sec,
            "max_hold_sec": max_hold_sec,
            "symbols": len(DataProvider.EXECUTION_WATCHLIST),
            "stats": stats_payload,
            "open_positions_at_end": len(positions),
            "batcher": batcher.stats,
            "execution": evidence,
            "checks": checks,
            "passed": all(checks.values()),
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return report
    finally:
        for task in consumers:
            task.cancel()
        batcher_task.cancel()
        await asyncio.gather(*consumers, batcher_task, return_exceptions=True)
        await bus.stop()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-sec", type=float, default=1200.0)
    parser.add_argument("--tick-hz", type=float, default=4.0)
    parser.add_argument("--report-sec", type=float, default=60.0)
    parser.add_argument("--signal-interval-sec", type=float, default=12.0)
    parser.add_argument("--max-hold-sec", type=float, default=90.0)
    parser.add_argument("--seed", type=int, default=20260531)
    parser.add_argument("--json-out", default="tmp/active_hours_soak_latest.json")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    report = asyncio.run(
        run_active_hours_soak(
            duration_sec=max(0.1, args.duration_sec),
            tick_hz=max(1.0, args.tick_hz),
            report_sec=max(1.0, args.report_sec),
            signal_interval_sec=max(0.1, args.signal_interval_sec),
            max_hold_sec=max(0.1, args.max_hold_sec),
            seed=args.seed,
            json_out=args.json_out,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
