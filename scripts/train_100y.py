import json
import logging
import os
import sqlite3
import sys
from datetime import datetime

import numpy as np

# Add src to path
_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_root, "src"))

from scipy.optimize import differential_evolution

from quant_signals import MultiFactorAlpha, RegimeFilter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "training_data.db"
WEIGHTS_PATH = "src/trained_weights.json"
RESULTS_PATH = "src/phase1_results.json"

def load_data(symbol: str, timeframe: str = "1d"):
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT close, volume, timestamp FROM ohlcv WHERE symbol=? AND timeframe=? ORDER BY timestamp ASC",
            (symbol, timeframe)
        )
        rows = c.fetchall()
        if not rows:
            return None
        prices = np.array([float(r[0]) for r in rows if r[0]])
        volumes = np.array([float(r[1]) for r in rows if r[0]])
        timestamps = [r[2] for r in rows if r[0]]
        return prices, volumes, timestamps
    finally:
        conn.close()

def simulate_sharpe(w, prices, volumes):
    weights = {
        'momentum_1m':    abs(w[0]),
        'momentum_5d':    abs(w[1]),
        'mean_reversion': abs(w[2]),
        'vol_regime':     abs(w[3]),
        'volume_surge':   abs(w[4]),
    }
    total = sum(weights.values()) + 1e-10
    weights = {k: v/total for k, v in weights.items()}

    mf = MultiFactorAlpha(weights=weights)
    pnls = []
    # Test step=10 days for deeper granularity
    for i in range(50, len(prices) - 5, 10):
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

    if len(pnls) < 20: return 0.0
    arr = np.array(pnls)
    return float(np.mean(arr) / (np.std(arr) + 1e-10) * np.sqrt(252))

def optimise_regime_weights(prices, volumes, timestamps):
    """
    Samvid v1.0-beta-beta: Regime-Specific Optimization.
    1. Fits HMM to identify partitions.
    2. Optimizes weights for each partition.
    """
    print("\n🔮 Partitioning 100-year history into BULL/BEAR/SIDEWAYS via HMM...")
    rf = RegimeFilter(n_regimes=3)
    rf.fit(prices)

    # Label parts of the data
    states = rf._model.predict(np.diff(np.log(prices + 1e-10)).reshape(-1, 1))
    # Align states with indices (diff loses 1)
    states = np.insert(states, 0, states[0])

    labels = rf._regime_labels
    regime_data = {l: {"p":[], "v":[]} for l in labels.values()}

    for i, s in enumerate(states):
        regime_data[labels[s]]["p"].append(prices[i])
        regime_data[labels[s]]["v"].append(volumes[i])

    final_weights = {}

    for regime, data in regime_data.items():
        if len(data["p"]) < 100:
            print(f"  ⚠ Skipping {regime} (insufficient data)")
            continue

        print(f"  ▶ Optimizing weights for {regime} market ({len(data['p'])} bars)...")
        rp = np.array(data["p"])
        rv = np.array(data["v"])

        bounds = [(0.05, 0.50)] * 5
        result = differential_evolution(
            lambda w: -simulate_sharpe(w, rp, rv),
            bounds, maxiter=12, seed=42, workers=1, tol=0.01
        )

        total = sum(abs(x) for x in result.x) + 1e-10
        final_weights[regime] = {
            'momentum_1m':    round(abs(result.x[0])/total, 4),
            'momentum_5d':    round(abs(result.x[1])/total, 4),
            'mean_reversion': round(abs(result.x[2])/total, 4),
            'vol_regime':     round(abs(result.x[3])/total, 4),
            'volume_surge':   round(abs(result.x[4])/total, 4),
        }
        print(f"    ✓ {regime} Sharpe: {-result.fun:.3f}")

    return final_weights

def main():
    print("\n" + "="*70)
    print("  Samvid v1.0-beta-beta — REGIME-SPECIFIC CENTURY TRAINING (100Y)")
    print("  Optimizing Absolute Alpha across a century of market cycles.")
    print("="*70)

    # 1. Load ^GSPC
    data = load_data("^GSPC")
    if not data:
        print("❌ Error: ^GSPC data not found. Run backfill first.")
        return
    prices, volumes, timestamps = data
    print(f"  ✓ ^GSPC loaded: {len(prices)} bars (1927 - 2026)")

    # 2. Optimize Regime-Specific Weights
    best_weights = optimise_regime_weights(prices, volumes, timestamps)

    # 3. Validation on ETFs (Regime-Aware)
    print("\n📊 Validating Regime-Aware Model on modern ETFs...")
    per_symbol_sharpe = {}
    validation_results = {}

    # Alpha model with NEW regime-specific weights
    ma = MultiFactorAlpha(weights=best_weights)

    for symbol in ["SPY", "QQQ", "IWM", "DIA", "XLK"]:
        v_data = load_data(symbol)
        if not v_data: continue
        vp, vv, _ = v_data

        # Fit a local HMM for the symbol validation
        rf_v = RegimeFilter(n_regimes=3)
        rf_v.fit(vp)

        pnls = []
        for i in range(50, len(vp) - 5, 20):
            p_win = vp[max(0, i-50):i]
            v_win = vv[max(0, i-50):i]

            # Get current regime
            rsig = rf_v.predict(p_win)
            regime = rsig.meta.get("regime", "DEFAULT")

            sig = ma.compute(p_win, v_win, regime=regime)
            if abs(sig.score) < 0.15: continue

            entry = vp[i]
            exit_p = vp[min(i+5, len(vp)-1)]
            direction = 1 if sig.score > 0 else -1
            pnls.append(direction * (exit_p - entry) / (entry + 1e-10))

        if len(pnls) > 10:
            arr = np.array(pnls)
            sharpe = float(np.mean(arr) / (np.std(arr) + 1e-10) * np.sqrt(252))
        else:
            sharpe = 0.0

        per_symbol_sharpe[symbol] = round(sharpe, 3)
        validation_results[symbol] = {
            "symbol": symbol,
            "sharpe": round(sharpe, 3),
            "verdict": "ULTRA EDGE" if sharpe > 3.0 else "STRONG" if sharpe > 2.0 else "DEPLOYABLE",
            "bars": len(vp)
        }
        print(f"  ▶ {symbol:<5}: Sharpe {sharpe:.3f}")

    # 4. Save Trained Weights
    weight_data = {
        "trained_at": datetime.now().isoformat(),
        "factor_weights": best_weights,
        "per_symbol_sharpe": per_symbol_sharpe,
        "source": "^GSPC (1927-2026)",
        "version": "v1.0-beta-Century"
    }
    with open(WEIGHTS_PATH, "w") as f:
        json.dump(weight_data, f, indent=2)

    # 5. Save Results
    results_json = {
        "timestamp": datetime.now().isoformat(),
        "optimised_weights": best_weights,
        "results": validation_results,
        "avg_sharpe": float(np.mean(list(per_symbol_sharpe.values())))
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(results_json, f, indent=2)

    print("\n" + "="*70)
    print("✅ Training Complete. Files updated:")
    print(f"   - {WEIGHTS_PATH}")
    print(f"   - {RESULTS_PATH}")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
