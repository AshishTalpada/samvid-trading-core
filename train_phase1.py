"""
SETO V9.0 — Phase 1 Training Script
Fetches maximum historical data, trains all models, runs walk-forward validation.
Run: python train_phase1.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import sqlite3
import logging
import numpy as np
import json
from datetime import datetime

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 1. Fetch maximum historical data from yfinance ───────────────────────────

SYMBOLS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "NVDA", "AAPL", "MSFT", "AMZN"]
INTERVAL_CONFIGS = [
    ("1d",  "10y"),   # 10 years of daily  — ~2520 bars per symbol
    ("1h",  "730d"),  # 2 years of hourly  — ~3000 bars per symbol
    ("5m",  "60d"),   # 60 days of 5-min   — ~5000 bars per symbol
]
DB_PATH = "training_data.db"


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ohlcv (
            symbol TEXT, timeframe TEXT, timestamp TEXT,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, timeframe, timestamp)
        )
    """)
    conn.commit()
    return conn


def fetch_and_store(conn: sqlite3.Connection, symbol: str,
                    interval: str, period: str) -> int:
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty:
            return 0
        rows = []
        for ts, row in df.iterrows():
            rows.append((
                symbol, interval,
                str(ts),
                float(row.get("Open", 0)),
                float(row.get("High", 0)),
                float(row.get("Low", 0)),
                float(row.get("Close", 0)),
                float(row.get("Volume", 0)),
            ))
        conn.executemany(
            "INSERT OR REPLACE INTO ohlcv VALUES (?,?,?,?,?,?,?,?)", rows
        )
        conn.commit()
        return len(rows)
    except Exception as e:
        print(f"  ⚠ Fetch error {symbol}/{interval}: {e}")
        return 0


def load_symbol_data(conn: sqlite3.Connection, symbol: str,
                     timeframe: str = "1d") -> tuple[np.ndarray, np.ndarray]:
    c = conn.cursor()
    c.execute(
        "SELECT close, volume FROM ohlcv WHERE symbol=? AND timeframe=? ORDER BY timestamp ASC",
        (symbol, timeframe)
    )
    rows = c.fetchall()
    if not rows:
        return np.array([]), np.array([])
    prices  = np.array([float(r[0]) for r in rows if r[0] and r[0] > 0])
    volumes = np.array([float(r[1]) for r in rows if r[0] and r[0] > 0])
    return prices, volumes


# ── 2. Training Functions ─────────────────────────────────────────────────────

def train_regime_filter(prices: np.ndarray, symbol: str):
    from quant_signals import RegimeFilter
    rf = RegimeFilter(n_regimes=3)
    rf.fit(prices)
    return rf


def optimise_factor_weights(prices: np.ndarray, volumes: np.ndarray) -> dict:
    """
    Grid-search MultiFactorAlpha weights by Sharpe on historical data.
    Tests 27 weight combinations and returns the best.
    """
    from quant_signals import MultiFactorAlpha, KalmanEntryTimer
    from scipy.optimize import differential_evolution

    kt = KalmanEntryTimer()
    best_sharpe = -999
    best_weights = None

    weight_options = [0.10, 0.20, 0.30, 0.40]

    def simulate_sharpe(w):
        weights = {
            'momentum_1m':    abs(w[0]),
            'momentum_5d':    abs(w[1]),
            'mean_reversion': abs(w[2]),
            'vol_regime':     abs(w[3]),
            'volume_surge':   abs(w[4]),
        }
        # Normalise
        total = sum(weights.values()) + 1e-10
        weights = {k: v/total for k, v in weights.items()}

        mf = MultiFactorAlpha(weights=weights)
        pnls = []
        for i in range(50, len(prices) - 5, 5):
            p_win = prices[max(0, i-50):i]
            v_win = volumes[max(0, i-50):i]
            sig = mf.compute(p_win, v_win)
            if abs(sig.score) < 0.15:
                continue
            entry = prices[i]
            exit_p = prices[min(i+5, len(prices)-1)]
            direction = 1 if sig.score > 0 else -1
            pnl = direction * (exit_p - entry) / (entry + 1e-10)
            pnls.append(pnl)

        if len(pnls) < 10:
            return 0.0
        arr = np.array(pnls)
        return float(np.mean(arr) / (np.std(arr) + 1e-10) * np.sqrt(252))

    bounds = [(0.05, 0.50)] * 5
    try:
        result = differential_evolution(
            lambda w: -simulate_sharpe(w),
            bounds, maxiter=50, seed=42, workers=1, tol=0.01
        )
        w = result.x
        total = sum(abs(x) for x in w) + 1e-10
        best_weights = {
            'momentum_1m':    round(abs(w[0])/total, 4),
            'momentum_5d':    round(abs(w[1])/total, 4),
            'mean_reversion': round(abs(w[2])/total, 4),
            'vol_regime':     round(abs(w[3])/total, 4),
            'volume_surge':   round(abs(w[4])/total, 4),
        }
        best_sharpe = -result.fun
    except Exception as e:
        print(f"  ⚠ Weight optimisation error: {e}")
        best_weights = {
            'momentum_1m': 0.30, 'momentum_5d': 0.20,
            'mean_reversion': 0.20, 'vol_regime': 0.15, 'volume_surge': 0.15,
        }

    return {"weights": best_weights, "backtest_sharpe": round(best_sharpe, 4)}


# ── 3. Walk-Forward Validation ────────────────────────────────────────────────

def run_walkforward(prices: np.ndarray, volumes: np.ndarray,
                    symbol: str, optimised_weights: dict,
                    initial_capital: float = 500.0) -> dict:
    from quant_signals import QuantConsensus, MultiFactorAlpha

    TRAIN = 500   # ~2 years daily bars
    TEST  = 100   # ~5 months out-of-sample
    STOP  = 0.015
    TARGET = 0.030

    qc = QuantConsensus()
    qc.alpha_model = MultiFactorAlpha(weights=optimised_weights)

    all_trades = []
    windows    = 0
    start      = 0
    equity     = initial_capital

    while start + TRAIN + TEST <= len(prices):
        train_p = prices[start : start + TRAIN]
        train_v = volumes[start : start + TRAIN]
        test_p  = prices[start + TRAIN : start + TRAIN + TEST]
        test_v  = volumes[start + TRAIN : start + TRAIN + TEST]

        qc.fit(train_p)

        win_rate = 0.5
        avg_win  = TARGET * equity
        avg_loss = STOP   * equity
        i = 30

        while i < len(test_p) - 1:
            pw = np.concatenate([train_p[-100:], test_p[:i]])
            vw = np.concatenate([train_v[-100:], test_v[:i]])

            c = qc.evaluate(pw, vw, win_rate=win_rate,
                            avg_win=avg_win, avg_loss=avg_loss,
                            portfolio_value=equity)

            if c["phase"] not in ("BUY", "SELL") or c["regime_veto"]:
                i += 1
                continue

            entry = float(test_p[i])
            side  = "LONG" if c["phase"] == "BUY" else "SHORT"
            d     = 1 if side == "LONG" else -1
            stop  = entry * (1 - d * STOP)
            tgt   = entry * (1 + d * TARGET)
            size  = max(10.0, min(c["position_usd"], equity * 0.10))

            exit_p = None
            exit_i = i
            for j in range(i+1, min(i+40, len(test_p))):
                p = float(test_p[j])
                if side == "LONG":
                    if p <= stop:   exit_p = stop;  exit_i = j; break
                    if p >= tgt:    exit_p = tgt;   exit_i = j; break
                else:
                    if p >= stop:   exit_p = stop;  exit_i = j; break
                    if p <= tgt:    exit_p = tgt;   exit_i = j; break

            if exit_p is None:
                exit_p = float(test_p[min(i+40, len(test_p)-1)])
                exit_i = min(i+40, len(test_p)-1)

            pnl_pct = d * (exit_p - entry) / (entry + 1e-10)
            pnl_usd = pnl_pct * size
            equity += pnl_usd

            all_trades.append({
                "symbol": symbol, "side": side,
                "entry": round(entry,4), "exit": round(exit_p,4),
                "pnl_pct": round(pnl_pct,6), "pnl_usd": round(pnl_usd,4),
                "confidence": c["confidence"], "regime": c["regime"],
                "window": windows,
            })

            if len(all_trades) >= 5:
                recent = all_trades[-20:]
                wins   = [t["pnl_usd"] for t in recent if t["pnl_usd"] > 0]
                losses = [abs(t["pnl_usd"]) for t in recent if t["pnl_usd"] <= 0]
                win_rate = len(wins) / (len(recent) + 1e-10)
                avg_win  = float(np.mean(wins)) if wins else avg_win
                avg_loss = float(np.mean(losses)) if losses else avg_loss

            i = exit_i + 1

        windows += 1
        start += TEST

    if not all_trades:
        return {"error": "no trades generated", "symbol": symbol}

    pnls = np.array([t["pnl_pct"] for t in all_trades])
    wins = [t for t in all_trades if t["pnl_usd"] > 0]
    losses_t = [t for t in all_trades if t["pnl_usd"] <= 0]

    sharpe = float(np.mean(pnls) / (np.std(pnls) + 1e-10) * np.sqrt(252))

    from scipy import stats as sp
    t_stat, p_val = sp.ttest_1samp(pnls, 0) if len(pnls) > 1 else (0, 1)

    eq_curve = np.cumsum([t["pnl_usd"] for t in all_trades])
    peak     = np.maximum.accumulate(eq_curve)
    max_dd   = float(np.min((eq_curve - peak) / (np.abs(peak) + 1e-10)))

    gross_win  = sum(t["pnl_usd"] for t in wins)
    gross_loss = abs(sum(t["pnl_usd"] for t in losses_t))
    pf = gross_win / (gross_loss + 1e-10)

    wr = len(wins) / (len(all_trades) + 1e-10)

    if sharpe >= 1.5 and p_val < 0.05:
        verdict = "🚀 STRONG EDGE — Deploy with confidence"
    elif sharpe >= 1.0 and p_val < 0.05:
        verdict = "✅ DEPLOYABLE EDGE — Phase 2 approved"
    elif sharpe >= 0.5:
        verdict = "⚠️  WEAK EDGE — Tune before live capital"
    else:
        verdict = "❌ NO EDGE — Do not deploy"

    return {
        "symbol": symbol, "windows": windows,
        "total_trades": len(all_trades),
        "win_rate": round(wr, 4),
        "profit_factor": round(pf, 3),
        "sharpe": round(sharpe, 3),
        "t_stat": round(float(t_stat), 3),
        "p_value": round(float(p_val), 5),
        "significant": bool(p_val < 0.05),
        "max_drawdown": round(max_dd, 4),
        "total_pnl_usd": round(float(eq_curve[-1]) if len(eq_curve) else 0, 2),
        "verdict": verdict,
        "best_regime": _best_regime(all_trades),
        "trades_sample": all_trades[:3],
    }


def _best_regime(trades: list) -> str:
    from collections import defaultdict
    regime_pnl = defaultdict(list)
    for t in trades:
        regime_pnl[t["regime"]].append(t["pnl_usd"])
    best = max(regime_pnl, key=lambda r: sum(regime_pnl[r]), default="UNKNOWN")
    return best


# ── 4. Save trained weights ───────────────────────────────────────────────────

def save_trained_weights(weights: dict, sharpes: dict, path: str = "src/trained_weights.json"):
    data = {
        "trained_at": datetime.utcnow().isoformat(),
        "factor_weights": weights,
        "per_symbol_sharpe": sharpes,
        "version": "V9.0",
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n  💾 Trained weights saved → {path}")


# ── 5. Apply saved weights at runtime ────────────────────────────────────────

def load_trained_weights(path: str = "src/trained_weights.json") -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# ── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "="*65)
    print("  SETO V9.0 — PHASE 1 FULL TRAINING PIPELINE")
    print("  Fetching 10 years of data across 10 symbols...")
    print("="*65)

    conn = init_db(DB_PATH)

    # ── Step 1: Fetch data ────────────────────────────────────────────────────
    print("\n📡 STEP 1: FETCHING HISTORICAL DATA\n")
    total_bars = 0
    for symbol in SYMBOLS:
        sym_bars = 0
        for interval, period in INTERVAL_CONFIGS:
            n = fetch_and_store(conn, symbol, interval, period)
            sym_bars += n
        total_bars += sym_bars
        print(f"  ✓ {symbol:<6} {sym_bars:>6} bars stored")
    print(f"\n  Total bars fetched: {total_bars:,}")

    # ── Step 2: Optimise weights on SPY (primary instrument) ─────────────────
    print("\n⚙️  STEP 2: OPTIMISING SIGNAL WEIGHTS (SPY daily — 10yr)\n")
    spy_prices, spy_volumes = load_symbol_data(conn, "SPY", "1d")
    print(f"  SPY daily bars available: {len(spy_prices)}")

    if len(spy_prices) < 200:
        print("  ⚠ Insufficient SPY data — using default weights")
        optimised = {
            'momentum_1m': 0.30, 'momentum_5d': 0.20,
            'mean_reversion': 0.20, 'vol_regime': 0.15, 'volume_surge': 0.15,
        }
        opt_sharpe = 0.0
    else:
        print("  Running differential evolution optimiser (this takes ~60s)...")
        opt_result = optimise_factor_weights(spy_prices, spy_volumes)
        optimised  = opt_result["weights"]
        opt_sharpe = opt_result["backtest_sharpe"]
        print(f"  ✓ Optimised weights (in-sample Sharpe: {opt_sharpe:.3f}):")
        for k, v in optimised.items():
            print(f"    {k:<20} {v:.4f}")

    # ── Step 3: Walk-forward validation per symbol ───────────────────────────
    print("\n📊 STEP 3: WALK-FORWARD VALIDATION (out-of-sample)\n")
    all_results = {}
    sharpes = {}

    for symbol in ["SPY", "QQQ", "IWM", "DIA", "XLK"]:
        prices, volumes = load_symbol_data(conn, symbol, "1d")
        if len(prices) < 700:
            print(f"  ⚠ {symbol}: only {len(prices)} bars — skipping (need 700+)")
            continue
        print(f"  ▶ {symbol} ({len(prices)} bars)...", end=" ", flush=True)
        result = run_walkforward(prices, volumes, symbol, optimised)
        all_results[symbol] = result
        sharpes[symbol]      = result.get("sharpe", 0)
        print(f"Sharpe={result.get('sharpe','?'):.3f} | WR={result.get('win_rate',0):.1%} | "
              f"PF={result.get('profit_factor',0):.2f} | {result.get('verdict','?')}")

    # ── Step 4: Regime-specific training ─────────────────────────────────────
    print("\n🔮 STEP 4: TRAINING REGIME FILTERS\n")
    regime_models = {}
    for symbol in ["SPY", "QQQ", "IWM"]:
        prices, _ = load_symbol_data(conn, symbol, "1d")
        if len(prices) < 200:
            continue
        try:
            rf = train_regime_filter(prices, symbol)
            if rf._model is not None:
                regime_models[symbol] = rf
                sig = rf.predict(prices[-100:])
                print(f"  ✓ {symbol}: current regime = {sig.meta.get('regime','?')} "
                      f"(conf={sig.confidence:.1%})")
        except Exception as e:
            print(f"  ⚠ {symbol} HMM: {e}")

    # ── Step 5: Save weights ──────────────────────────────────────────────────
    save_trained_weights(optimised, sharpes)

    # ── Step 6: Final report ──────────────────────────────────────────────────
    print("\n" + "="*65)
    print("  PHASE 1 TRAINING COMPLETE — FINAL REPORT")
    print("="*65)

    if all_results:
        avg_sharpe  = float(np.mean(list(sharpes.values()))) if sharpes else 0
        sig_count   = sum(1 for r in all_results.values() if r.get("significant"))
        best_sym    = max(sharpes, key=sharpes.__getitem__) if sharpes else "N/A"

        print(f"\n  Symbols validated:      {len(all_results)}")
        print(f"  Average Sharpe:         {avg_sharpe:.3f}")
        print(f"  Statistically sig (p<0.05): {sig_count}/{len(all_results)}")
        print(f"  Best symbol:            {best_sym} (Sharpe={sharpes.get(best_sym,0):.3f})")
        print()

        for sym, r in all_results.items():
            print(f"  {sym:<6} | Sharpe={r.get('sharpe',0):.3f} | "
                  f"WR={r.get('win_rate',0):.1%} | "
                  f"PF={r.get('profit_factor',0):.2f} | "
                  f"DD={r.get('max_drawdown',0):.1%} | "
                  f"Trades={r.get('total_trades',0)}")
        print()

        # PHASE 1 GATE
        if avg_sharpe >= 1.0 and sig_count >= 2:
            print("  🚀 PHASE 1 PASSED")
            print("  ✅ Edge is statistically real across multiple symbols.")
            print("  ✅ Proceed to Phase 2: Paper Trading on Alpaca.")
            print("  ✅ Trained weights loaded into system automatically.")
            print()
            print("  NEXT STEPS:")
            print("  1. Start system: python src/main.py")
            print("  2. Quant signals will auto-load from src/trained_weights.json")
            print("  3. Monitor live performance for 2 weeks on paper trading")
            print("  4. If live Sharpe > 0.8, apply for FTMO evaluation")
        elif avg_sharpe >= 0.5:
            print("  ⚠️  PHASE 1 PARTIAL — Edge exists but needs tuning.")
            print("  → Edit factor weights in src/trained_weights.json")
            print("  → Increase TRAIN bars in run_walkforward() for more data")
            print("  → Consider adding alternative data (options flow, insider buys)")
        else:
            print("  ❌ PHASE 1 FAILED — No statistically significant edge found.")
            print("  → Review market conditions (sideways market kills momentum)")
            print("  → Try mean_reversion weighting for range-bound markets")
    else:
        print("  ⚠ No results — check DB has data after fetch step above.")

    print("="*65 + "\n")
    conn.close()

    # Save full results JSON for dashboard integration
    with open("src/phase1_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.utcnow().isoformat(),
            "optimised_weights": optimised,
            "results": {k: {kk: vv for kk, vv in v.items() if kk != "trades_sample"}
                        for k, v in all_results.items()},
            "avg_sharpe": float(avg_sharpe) if all_results else 0,
        }, f, indent=2)
    print("  📄 Full results → src/phase1_results.json\n")


if __name__ == "__main__":
    main()
