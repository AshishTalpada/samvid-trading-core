"""
Validates edge with statistical rigour before deploying capital.
Run: python -m src.backtest_engine
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_db_lock = asyncio.Lock()

PHASE1_MIN_PROFIT_FACTOR = 1.30
PHASE1_MAX_DRAWDOWN = 0.12
PHASE1_MAX_P_VALUE = 0.05


@dataclass
class Trade:
    symbol: str
    entry_price: float
    exit_price: float
    entry_idx: int
    exit_idx: int
    side: str  # 'LONG' | 'SHORT'
    commission: float = 1.0  # IBKR/MT5 estimated round-trip
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    size_usd: float = 0.0

    def __post_init__(self):
        from decimal import Decimal

        d_entry = Decimal(str(self.entry_price))
        d_exit = Decimal(str(self.exit_price))
        d_size = Decimal(str(self.size_usd))
        d_comm = Decimal(str(self.commission))

        direction = Decimal("1") if self.side == "LONG" else Decimal("-1")

        # Use a small epsilon for division to avoid ZeroDivisionError
        self.pnl_pct = float(direction * (d_exit - d_entry) / (d_entry + Decimal("1e-12")))
        self.pnl_usd = float((Decimal(str(self.pnl_pct)) * d_size) - d_comm)


@dataclass
class WalkForwardResult:
    symbol: str
    window_start: int
    window_end: int
    trades: list[Trade] = field(default_factory=list)

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if t.pnl_usd > 0) / len(self.trades)

    @property
    def total_pnl_usd(self) -> float:
        return sum(t.pnl_usd for t in self.trades)

    @property
    def avg_win(self) -> float:
        wins = [t.pnl_usd for t in self.trades if t.pnl_usd > 0]
        return float(np.mean(wins)) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [abs(t.pnl_usd) for t in self.trades if t.pnl_usd <= 0]
        return float(np.mean(losses)) if losses else 1.0

    @property
    def profit_factor(self) -> float:
        gross_win = sum(t.pnl_usd for t in self.trades if t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in self.trades if t.pnl_usd <= 0))
        return gross_win / (gross_loss + 1e-10)

    @property
    def sharpe(self) -> float:
        if len(self.trades) < 3:
            return 0.0
        pnls = np.array([t.pnl_pct for t in self.trades])
        # Annualized assuming ~1 trade/day; see sharpe_per_trade for the raw ratio.
        return float(np.mean(pnls) / (np.std(pnls) + 1e-10) * np.sqrt(252))

    @property
    def sharpe_per_trade(self) -> float:
        """Raw per-trade Sharpe (mean/std of trade returns) with no annualization assumption."""
        if len(self.trades) < 3:
            return 0.0
        pnls = np.array([t.pnl_pct for t in self.trades])
        return float(np.mean(pnls) / (np.std(pnls) + 1e-10))

    @property
    def max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        equity = np.cumsum([t.pnl_usd for t in self.trades])
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / (np.abs(peak) + 1e-10)
        return float(np.min(dd))


async def load_ohlcv_from_db(
    db_path: str, symbol: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """
    Load OHLCV from SQLite.
    Returns (opens, highs, lows, closes, volumes, timestamps).
    Uses global _db_lock to prevent contention during parallel validation bursts.
    """
    async with _db_lock:
        try:

            def _load():
                conn = sqlite3.connect(db_path, timeout=60.0)
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                # Load open/high/low/close for realistic intra-bar simulation
                cursor.execute(
                    "SELECT timestamp, open, high, low, close, volume FROM ohlcv "
                    "WHERE symbol=? ORDER BY timestamp ASC",
                    (symbol,),
                )
                rows = cursor.fetchall()
                conn.close()
                return rows

            rows = await asyncio.to_thread(_load)

            if not rows:
                return np.array([]), np.array([]), np.array([]), np.array([]), []
            timestamps = [r[0] for r in rows]
            opens = np.array([float(r[1]) for r in rows])
            highs = np.array([float(r[2]) for r in rows])
            lows = np.array([float(r[3]) for r in rows])
            closes = np.array([float(r[4]) for r in rows])
            return opens, highs, lows, closes, timestamps
        except Exception as e:
            logger.error(f"DB load failed for {symbol}: {e}")
            return np.array([]), np.array([]), np.array([]), np.array([]), []


class WalkForwardEngine:
    """
    Validates trading edge across multiple out-of-sample windows.
    Train on N bars → Test on M bars → Roll forward → Repeat.
    Minimum 6 cycles for statistical significance.
    """

    def __init__(
        self,
        db_path: str = "data/trading.db",
        train_bars: int = 1000,  # ~5 months of 1min bars per session
        test_bars: int = 200,  # ~1 month out-of-sample
        stop_loss_pct: float = 0.015,  # 1.5% stop
        take_profit_pct: float = 0.030,  # 3.0% target (2:1 R:R)
        initial_capital: float = 500.0,
        slippage_pct: float = 0.0005,  # 0.05% slippage (5 bps)
        spread_pct: float = 0.0010,  # 0.10% average bid/ask spread
        commission: float = 1.0,  # $1 per trade estimate
    ):
        from quant_signals import QuantConsensus

        self.db_path = db_path
        self.train_bars = train_bars
        self.test_bars = test_bars
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.capital = initial_capital
        self.SLIPPAGE_PCT = slippage_pct
        self.SPREAD_PCT = spread_pct
        self.COMMISSION_USD = commission
        self.consensus = QuantConsensus()

    async def run(self, symbol: str) -> list[WalkForwardResult]:
        result_tuple = await load_ohlcv_from_db(self.db_path, symbol)
        opens, highs, lows, closes, timestamps = result_tuple

        if len(closes) < self.train_bars + self.test_bars:
            logger.warning(
                f"{symbol}: insufficient data ({len(closes)} bars). Need {self.train_bars + self.test_bars}"
            )
            return []

        results: list[WalkForwardResult] = []
        start = 0

        while start + self.train_bars + self.test_bars <= len(closes):
            train_end = start + self.train_bars
            test_end = train_end + self.test_bars

            train_closes = closes[start:train_end]
            test_closes = closes[train_end:test_end]
            test_highs = highs[train_end:test_end]
            test_lows = lows[train_end:test_end]

            # Fit models on training window
            self.consensus.fit(train_closes)

            # Simulate on test window
            win_rate = 0.5  # initial estimate, updates after first trades
            avg_win = self.stop_loss_pct * 2.0
            avg_loss = self.stop_loss_pct

            result = WalkForwardResult(symbol=symbol, window_start=train_end, window_end=test_end)
            equity = self.capital

            i = 50  # minimum lookback before first signal
            while i < len(test_closes) - 1:
                p_window = np.concatenate([train_closes[-100:], test_closes[:i]])
                v_window = np.concatenate([train_closes[-100:], test_closes[:i]])

                consensus = self.consensus.evaluate(
                    symbol,
                    p_window,
                    v_window,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    portfolio_value=equity,
                )

                phase = consensus["phase"]
                if phase not in ("BUY", "SELL") or consensus["regime_veto"]:
                    i += 1
                    continue

                side = "LONG" if phase == "BUY" else "SHORT"
                direction = 1 if side == "LONG" else -1

                # Entry at next bar Close (conservative proxy for Next Open)
                entry_raw = float(test_closes[i + 1])
                friction = self.SLIPPAGE_PCT + (self.SPREAD_PCT / 2.0)
                entry = entry_raw * (1 + friction) if side == "LONG" else entry_raw * (1 - friction)

                size_usd = max(10.0, min(consensus["position_usd"], equity * 0.10))
                stop = entry * (1 - direction * self.stop_loss_pct)
                target = entry * (1 + direction * self.take_profit_pct)

                # Find exit — check intra-bar HIGH/LOW first (realistic stop/target triggering)
                exit_price = None
                exit_idx = i + 1
                for j in range(i + 2, min(i + 61, len(test_closes))):
                    bar_high = float(test_highs[j])
                    bar_low = float(test_lows[j])
                    friction = self.SLIPPAGE_PCT + (self.SPREAD_PCT / 2.0)

                    if side == "LONG":
                        # Check stop via intra-bar LOW (more realistic than only close)
                        if bar_low <= stop:
                            exit_price = stop * (1 - friction)  # fill at stop accounting for gap
                            exit_idx = j
                            break
                        if bar_high >= target:
                            exit_price = target * (1 - friction)
                            exit_idx = j
                            break
                    else:  # SHORT
                        # Check stop via intra-bar HIGH
                        if bar_high >= stop:
                            exit_price = stop * (1 + friction)
                            exit_idx = j
                            break
                        if bar_low <= target:
                            exit_price = target * (1 + friction)
                            exit_idx = j
                            break

                if exit_price is None:
                    exit_price = float(test_closes[min(i + 60, len(test_closes) - 1)])
                    exit_idx = min(i + 60, len(test_closes) - 1)

                trade = Trade(
                    symbol=symbol,
                    entry_price=entry,
                    exit_price=exit_price,
                    entry_idx=i,
                    exit_idx=exit_idx,
                    side=side,
                    size_usd=size_usd,
                    commission=self.COMMISSION_USD,
                )
                result.trades.append(trade)
                equity += trade.pnl_usd

                # Update rolling stats for Kelly sizing
                if result.n_trades >= 5:
                    win_rate = result.win_rate
                    avg_win = result.avg_win or avg_win
                    avg_loss = result.avg_loss or avg_loss

                i = exit_idx + 1  # no overlapping trades

            results.append(result)
            logger.info(
                f"Window {len(results):02d} [{train_end}-{test_end}] | "
                f"Trades: {result.n_trades:3d} | WR: {result.win_rate:.1%} | "
                f"PF: {result.profit_factor:.2f} | Sharpe: {result.sharpe:.2f} | "
                f"PnL: ${result.total_pnl_usd:+.2f} | MaxDD: {result.max_drawdown:.1%}"
            )
            start += self.test_bars  # roll forward

        return results


def aggregate_results(results: list[WalkForwardResult]) -> dict:
    """Compute portfolio-level statistics across all walk-forward windows."""
    if not results:
        return {"error": "No results"}

    all_trades = [t for r in results for t in r.trades]
    all_pnl_pct = np.array([t.pnl_pct for t in all_trades]) if all_trades else np.array([0.0])

    total_trades = len(all_trades)
    total_pnl_usd = sum(t.pnl_usd for t in all_trades)
    expectancy_net_usd = total_pnl_usd / total_trades if total_trades else 0.0
    win_rate = sum(1 for t in all_trades if t.pnl_usd > 0) / (total_trades + 1e-10)
    avg_win = (
        float(np.mean([t.pnl_usd for t in all_trades if t.pnl_usd > 0]))
        if any(t.pnl_usd > 0 for t in all_trades)
        else 0
    )
    avg_loss = (
        float(np.mean([abs(t.pnl_usd) for t in all_trades if t.pnl_usd <= 0]))
        if any(t.pnl_usd <= 0 for t in all_trades)
        else 1
    )

    gross_win = sum(t.pnl_usd for t in all_trades if t.pnl_usd > 0)
    gross_loss = abs(sum(t.pnl_usd for t in all_trades if t.pnl_usd <= 0))
    profit_factor = gross_win / (gross_loss + 1e-10)

    # 'sharpe' is annualized assuming ~1 trade/day; 'sharpe_per_trade' is the raw ratio,
    # which reviewers should rely on when the real trade cadence differs from daily.
    sharpe = float(np.mean(all_pnl_pct) / (np.std(all_pnl_pct) + 1e-10) * np.sqrt(252))
    sharpe_per_trade = float(np.mean(all_pnl_pct) / (np.std(all_pnl_pct) + 1e-10))

    # t-statistic: is the mean return statistically different from 0?
    from scipy import stats as sp_stats

    t_stat, p_value = sp_stats.ttest_1samp(all_pnl_pct, 0) if len(all_pnl_pct) > 1 else (0.0, 1.0)

    # Max drawdown across all windows
    equity_curve = np.cumsum([t.pnl_usd for t in all_trades])
    peak = np.maximum.accumulate(equity_curve)
    max_dd = (
        float(np.min((equity_curve - peak) / (np.abs(peak) + 1e-10)))
        if len(equity_curve) > 0
        else 0.0
    )

    verdict = (
        " NO EDGE"
        if sharpe < 0.5
        else " WEAK EDGE"
        if sharpe < 1.0
        else " DEPLOYABLE EDGE"
        if sharpe < 1.5
        else " STRONG EDGE"
    )

    result = {
        "verdict": verdict,
        "sharpe": round(sharpe, 3),
        "sharpe_per_trade": round(sharpe_per_trade, 4),
        "t_statistic": round(float(t_stat), 3),
        "p_value": round(float(p_value), 4),
        "statistically_significant": bool(p_value < 0.05),
        "total_trades": total_trades,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 3),
        "expectancy_net_usd": round(expectancy_net_usd, 4),
        "avg_win_usd": round(avg_win, 2),
        "avg_loss_usd": round(avg_loss, 2),
        "total_pnl_usd": round(total_pnl_usd, 2),
        "max_drawdown": round(max_dd, 4),
        "n_windows": len(results),
        "per_window_sharpe": [round(r.sharpe, 3) for r in results],
    }

    return result


def phase1_gate_report(
    all_symbol_results: dict[str, dict],
    *,
    min_profit_factor: float = PHASE1_MIN_PROFIT_FACTOR,
    max_drawdown: float = PHASE1_MAX_DRAWDOWN,
    max_p_value: float = PHASE1_MAX_P_VALUE,
) -> dict:
    """Evaluate Phase 1 with objective promotion gates from the roadmap."""
    symbol_reports: dict[str, dict] = {}
    required_passes = len(all_symbol_results) // 2 + 1

    for symbol, stats in all_symbol_results.items():
        expectancy = float(stats.get("expectancy_net_usd", 0.0) or 0.0)
        profit_factor = float(stats.get("profit_factor", 0.0) or 0.0)
        p_value = float(stats.get("p_value", 1.0) or 1.0)
        sharpe_per_trade = float(stats.get("sharpe_per_trade", 0.0) or 0.0)
        max_dd = abs(float(stats.get("max_drawdown", 1.0) or 0.0))

        blockers = []
        if p_value >= max_p_value:
            blockers.append(f"p_value {p_value:.4f} >= {max_p_value:.4f}")
        if profit_factor < min_profit_factor:
            blockers.append(f"profit_factor {profit_factor:.3f} < {min_profit_factor:.3f}")
        if expectancy <= 0:
            blockers.append(f"expectancy_net_usd {expectancy:.4f} <= 0")
        if sharpe_per_trade <= 0:
            blockers.append(f"sharpe_per_trade {sharpe_per_trade:.4f} <= 0")
        if max_dd > max_drawdown:
            blockers.append(f"max_drawdown {max_dd:.4f} > {max_drawdown:.4f}")

        symbol_reports[symbol] = {
            "passed": not blockers,
            "blockers": blockers,
            "metrics": {
                "p_value": p_value,
                "profit_factor": profit_factor,
                "expectancy_net_usd": expectancy,
                "sharpe_per_trade": sharpe_per_trade,
                "max_drawdown": max_dd,
            },
        }

    passed_symbols = [symbol for symbol, report in symbol_reports.items() if report["passed"]]
    significant_symbols = [
        symbol
        for symbol, stats in all_symbol_results.items()
        if float(stats.get("p_value", 1.0) or 1.0) < max_p_value
    ]

    return {
        "passed": bool(all_symbol_results) and len(passed_symbols) >= required_passes,
        "required_passes": required_passes,
        "passed_symbols": passed_symbols,
        "significant_symbols": significant_symbols,
        "symbol_reports": symbol_reports,
    }


async def run_phase1_validation(
    db_path: str = "data/trading.db", symbols: Optional[list[str]] = None, capital: float = 500.0
) -> None:
    """
    Run full Phase 1 validation.
    """
    if symbols is None:
        symbols = ["SPY", "QQQ", "IWM"]

    print("\n" + "=" * 65)
    print("  PHASE 1: WALK-FORWARD EDGE VALIDATION")
    print("=" * 65)

    all_symbol_results = {}

    async def run_one(symbol):
        # Slightly stagger start times to prevent absolute simultaneous DB hits
        await asyncio.sleep(np.random.uniform(0.1, 0.5))
        print(f" Starting walk-forward for {symbol}...")
        engine = WalkForwardEngine(db_path=db_path, initial_capital=capital)
        windows = await engine.run(symbol)

        if not windows:
            print(f"   {symbol}: Not enough data in DB.")
            return symbol, None

        stats = aggregate_results(windows)
        return symbol, stats

    # Run symbols in parallel (Sovereign Parallelism)
    tasks = [run_one(s) for s in symbols]
    completed = await asyncio.gather(*tasks)

    for symbol, stats in completed:
        if stats:
            all_symbol_results[symbol] = stats
            print(f"\n  ── {symbol} RESULTS ──")
            for k, v in stats.items():
                if k != "per_window_sharpe":
                    print(f"  {k:<32} {v}")
            print(f"  per_window_sharpe: {stats['per_window_sharpe']}")

    # Overall verdict
    print("\n" + "=" * 65)
    print("  OVERALL PHASE 1 VERDICT")
    print("=" * 65)
    if all_symbol_results:
        avg_sharpe = np.mean([v["sharpe"] for v in all_symbol_results.values()])
        gate = phase1_gate_report(all_symbol_results)
        sig_count = len(gate["significant_symbols"])
        print(f"  Average Sharpe across symbols: {avg_sharpe:.3f}")
        print(f"  Statistically significant symbols: {sig_count}/{len(all_symbol_results)}")
        print(
            "  Symbols passing all gates: "
            f"{len(gate['passed_symbols'])}/{len(all_symbol_results)} "
            f"(required {gate['required_passes']})"
        )

        if gate["passed"]:
            print("\n   PHASE 1 PASSED — Edge is real. Proceed to Phase 2 (Live Paper Trading).")
            return True
        print("\n   PHASE 1 FAILED - Do not deploy live capital.")
        for symbol, report in gate["symbol_reports"].items():
            if report["passed"]:
                continue
            print(f"  {symbol} blockers:")
            for blocker in report["blockers"]:
                print(f"    - {blocker}")
        return False
    else:
        print("\n   CRITICAL: No results generated. Check database integrity.")
        return False
    print("=" * 65 + "\n")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db = sys.argv[1] if len(sys.argv) > 1 else "data/trading.db"
    syms = sys.argv[2:] if len(sys.argv) > 2 else None
    asyncio.run(run_phase1_validation(db_path=db, symbols=syms))
