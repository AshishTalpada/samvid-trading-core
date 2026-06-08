#!/usr/bin/env python3
"""Per-signal Information Coefficient (IC) diagnostic.

Measures whether each QuantConsensus sub-signal actually predicts forward returns,
*before* any trade simulation, stops, or commissions. The IC is the correlation
between a signal's score at bar t and the realised forward return over the next H
bars. A signal with no predictive power has IC ~ 0; a useful signal has a small but
statistically significant positive IC (|IC| of 0.02-0.05 is already meaningful in
liquid markets). A significantly *negative* IC means the signal is anti-predictive.

This is a research diagnostic, not a trade backtest. It deliberately does not tune
parameters or simulate fills.

Usage:
    python scripts/signal_ic_diagnostic.py
    python scripts/signal_ic_diagnostic.py --db data/trading.db --symbols SPY,QQQ,IWM
    python scripts/signal_ic_diagnostic.py --horizon 10 --stride 5 --lookback 200
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for _path in (ROOT, SRC):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def compute_ic(scores: list[float], forward_returns: list[float]) -> dict[str, Any]:
    """Return Pearson + Spearman IC (with p-values) between scores and forward returns."""
    from scipy import stats

    s = np.asarray(scores, dtype=float)
    f = np.asarray(forward_returns, dtype=float)
    mask = np.isfinite(s) & np.isfinite(f)
    s, f = s[mask], f[mask]
    n = int(s.size)
    if n < 10 or np.std(s) < 1e-12 or np.std(f) < 1e-12:
        return {"n": n, "pearson_r": 0.0, "pearson_p": 1.0, "spearman_r": 0.0, "spearman_p": 1.0}
    pearson_r, pearson_p = stats.pearsonr(s, f)
    spearman_r, spearman_p = stats.spearmanr(s, f)
    return {
        "n": n,
        "pearson_r": float(pearson_r),
        "pearson_p": float(pearson_p),
        "spearman_r": float(spearman_r),
        "spearman_p": float(spearman_p),
    }


def _load_close_volume(db_path: str, symbol: str) -> tuple[np.ndarray, np.ndarray]:
    """Load close+volume for the densest timeframe (mirrors backtest_engine loader)."""
    path = Path(db_path)
    if not path.exists():
        return np.array([]), np.array([])
    conn = sqlite3.connect(str(path), timeout=60.0)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ohlcv)").fetchall()}
        if not cols:
            return np.array([]), np.array([])
        selected_tf = None
        if "timeframe" in cols:
            row = conn.execute(
                "SELECT timeframe, COUNT(*) AS c FROM ohlcv WHERE symbol=? "
                "GROUP BY timeframe ORDER BY c DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            selected_tf = row[0] if row else None
        if selected_tf is not None:
            rows = conn.execute(
                "SELECT close, volume FROM ohlcv WHERE symbol=? AND timeframe=? "
                "ORDER BY timestamp ASC",
                (symbol, selected_tf),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT close, volume FROM ohlcv WHERE symbol=? ORDER BY timestamp ASC",
                (symbol,),
            ).fetchall()
    finally:
        conn.close()
    if not rows:
        return np.array([]), np.array([])
    closes = np.array([float(r[0]) for r in rows])
    volumes = np.array([float(r[1] or 0.0) for r in rows])
    return closes, volumes


def signal_ics_for_symbol(
    closes: np.ndarray,
    volumes: np.ndarray,
    symbol: str,
    *,
    horizon: int = 10,
    stride: int = 5,
    lookback: int = 200,
) -> dict[str, dict[str, Any]]:
    """Compute IC for each standalone signal score against H-bar forward returns."""
    from quant_signals import KalmanEntryTimer, MultiFactorAlpha

    alpha_model = MultiFactorAlpha()
    collected: dict[str, list[float]] = {"alpha": [], "kalman": [], "combined": []}
    fwds: list[float] = []

    start = max(lookback, 30)
    end = len(closes) - horizon
    for i in range(start, end, stride):
        window_p = closes[i - lookback : i + 1]
        window_v = volumes[i - lookback : i + 1]
        if len(window_p) < 30:
            continue
        alpha_score = alpha_model.compute(window_p, window_v).score
        # Fresh Kalman per sample so state cannot leak across non-contiguous samples.
        kalman_score = KalmanEntryTimer().compute(symbol, window_p).score
        fwd = float((closes[i + horizon] - closes[i]) / (closes[i] + 1e-12))
        collected["alpha"].append(alpha_score)
        collected["kalman"].append(kalman_score)
        collected["combined"].append(alpha_score + kalman_score)
        fwds.append(fwd)

    return {name: compute_ic(scores, fwds) for name, scores in collected.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Per-signal Information Coefficient diagnostic.")
    parser.add_argument("--db", default=str(ROOT / "data" / "trading.db"))
    parser.add_argument("--symbols", default="SPY,QQQ,IWM")
    parser.add_argument("--horizon", type=int, default=10, help="Forward-return horizon in bars.")
    parser.add_argument("--stride", type=int, default=5, help="Sample every Nth bar.")
    parser.add_argument("--lookback", type=int, default=200, help="Trailing window per sample.")
    args = parser.parse_args(argv)

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    print("=" * 78)
    print(f"  SIGNAL IC DIAGNOSTIC  (horizon={args.horizon} bars, stride={args.stride})")
    print("  IC = corr(signal score @ t, forward return over next H bars). |IC|>0.02 w/ p<0.05 = real.")
    print("=" * 78)

    for symbol in symbols:
        closes, volumes = _load_close_volume(args.db, symbol)
        if closes.size < args.lookback + args.horizon + 10:
            print(f"\n  {symbol}: insufficient data ({closes.size} bars).")
            continue
        ics = signal_ics_for_symbol(
            closes, volumes, symbol,
            horizon=args.horizon, stride=args.stride, lookback=args.lookback,
        )
        print(f"\n  -- {symbol} ({closes.size} bars) --")
        print(f"  {'signal':<10} {'n':>6} {'pearson_IC':>12} {'p':>9} {'spearman_IC':>13} {'p':>9}  verdict")
        for name, ic in ics.items():
            sig = "PREDICTIVE" if (ic["pearson_p"] < 0.05 and ic["pearson_r"] > 0) else (
                "ANTI-PREDICTIVE" if (ic["pearson_p"] < 0.05 and ic["pearson_r"] < 0) else "no signal"
            )
            print(
                f"  {name:<10} {ic['n']:>6} {ic['pearson_r']:>12.4f} {ic['pearson_p']:>9.4f} "
                f"{ic['spearman_r']:>13.4f} {ic['spearman_p']:>9.4f}  {sig}"
            )
    print("\n" + "=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
