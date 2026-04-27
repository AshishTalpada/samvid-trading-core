import json
import logging
import os
import sys

import numpy as np
from scipy.optimize import differential_evolution

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from quant_signals import MultiFactorAlpha

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HardcoreTrainer")

def generate_adversarial_data(scenario: str, length: int = 5000):
    """Generates synthetic 'Hardcore' market regimes."""
    np.random.seed(42)
    base = 100.0
    returns = []

    if scenario == "BLACK_SWAN":
        # Sudden -20% crashes followed by massive volatility
        for i in range(length):
            if i % 1000 == 0:
                returns.append(-0.20) # Crash
            else:
                returns.append(np.random.normal(0, 0.03))
    elif scenario == "STOP_HUNTER":
        # Ranges with sudden spikes to 'hunt' stops
        for i in range(length):
            if i % 50 == 0:
                returns.append(np.random.choice([0.05, -0.05]))
            else:
                returns.append(np.random.normal(0, 0.005))
    elif scenario == "HYPER_TREND":
        # Parabolic move with no pullbacks
        returns = [0.005 + np.random.normal(0, 0.001) for _ in range(length)]
    else: # CHOP
        returns = [np.random.normal(0, 0.01) for _ in range(length)]

    prices = base * np.exp(np.cumsum(returns))
    volumes = np.random.randint(100000, 500000, length).astype(float)
    return prices, volumes

def evaluate_hardcore(w, scenarios_data):
    """Evaluate weights against ALL scenarios simultaneously."""
    weights = {
        'momentum_1m': abs(w[0]),
        'momentum_5d': abs(w[1]),
        'mean_reversion': abs(w[2]),
        'vol_regime': abs(w[3]),
        'volume_surge': abs(w[4]),
    }
    total = sum(weights.values()) + 1e-10
    weights = {k: v/total for k, v in weights.items()}

    mf = MultiFactorAlpha(weights=weights)
    total_score = 0

    for p, v in scenarios_data:
        pnls = []
        for i in range(50, len(p) - 5, 20):
            sig = mf.compute(p[max(0, i-50):i], v[max(0, i-50):i])
            if abs(sig.score) < 0.15: continue

            pnl = (1 if sig.score > 0 else -1) * (p[i+1] - p[i]) / p[i]
            pnls.append(pnl)

        if not pnls: continue
        arr = np.array(pnls)
        sharpe = np.mean(arr) / (np.std(arr) + 1e-10) * np.sqrt(252)
        mdd = np.max(np.maximum.accumulate(np.cumsum(arr)) - np.cumsum(arr))

        # Scoring: High Sharpe + Low Drawdown
        total_score += sharpe - (mdd * 10)

    return -total_score # Minimization

def train_hardcore():
    print("\n⚔️ ENTERING HARDCORE ADVERSARIAL TRAINING (360-DEGREE)...")
    scenarios = ["BLACK_SWAN", "STOP_HUNTER", "HYPER_TREND", "CHOP"]
    data = [generate_adversarial_data(s) for s in scenarios]

    print(f"  ▶ Throwing {len(scenarios)} extreme scenarios at the system...")

    bounds = [(0.05, 0.50)] * 5
    result = differential_evolution(
        evaluate_hardcore,
        bounds,
        args=(data,),
        maxiter=15,
        seed=42,
        workers=1
    )

    total = sum(abs(x) for x in result.x) + 1e-10
    final_w = {
        'momentum_1m': round(abs(result.x[0])/total, 4),
        'momentum_5d': round(abs(result.x[1])/total, 4),
        'mean_reversion': round(abs(result.x[2])/total, 4),
        'vol_regime': round(abs(result.x[3])/total, 4),
        'volume_surge': round(abs(result.x[4])/total, 4),
    }

    print("\n✅ HARDCORE TRAINING TO THE BONE COMPLETE.")
    print(f"  New 'Universal Sovereign' Weights: {json.dumps(final_w, indent=2)}")

    # Save as 'UNBREAKABLE' weight profile
    with open("src/unbreakable_weights.json", "w") as f:
        json.dump(final_w, f, indent=2)
    print("  ✓ Saved to src/unbreakable_weights.json")

if __name__ == "__main__":
    train_hardcore()
