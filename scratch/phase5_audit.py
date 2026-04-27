
import asyncio
import json
import logging
import sys
from pathlib import Path

# Mock Classes to simulate Agent D behavior
class ExpectancyData:
    def __init__(self, pattern, regime, session, n, wins, total_r, weighted_n, weighted_wins, weighted_r):
        self.pattern = pattern
        self.regime = regime
        self.session = session
        self.n_trades = n
        self.wins = wins
        self.total_r = total_r
        self.weighted_n = weighted_n
        self.weighted_wins = weighted_wins
        self.weighted_r = weighted_r
        self.win_rate = weighted_wins / weighted_n if weighted_n > 0 else (wins / n if n > 0 else 0.0)
        self.avg_r = weighted_r / weighted_n if weighted_n > 0 else (total_r / n if n > 0 else 0.0)
        self.data_rating = "STRONG" if n > 200 else "MODERATE"

class ConditionalExpectancyMatrix:
    def __init__(self, prior_path):
        self.matrix = {}
        self.priors = json.loads(Path(prior_path).read_text())
        self.activated = True
    
    def build(self, trade_history):
        raw = {}
        n_live = len(trade_history)
        
        # 1. Priors
        for pattern, regimes in self.priors.items():
            for regime, stats in regimes.items():
                key = f"{pattern}|{regime}|RTH"
                raw[key] = {
                    "pattern": pattern, "regime": regime, "session": "RTH",
                    "n": stats["n"], "wins": int(stats["n"] * stats["win_rate"]),
                    "total_r": stats["n"] * stats["avg_r"],
                    "weighted_n": float(stats["n"]), "weighted_wins": float(stats["n"] * stats["win_rate"]),
                    "weighted_r": float(stats["n"] * stats["avg_r"])
                }
        
        # 2. Live
        import math
        for i, trade in enumerate(trade_history):
            key = f"{trade['pattern']}|{trade['regime']}|{trade['session']}"
            if key not in raw:
                raw[key] = {"pattern": trade['pattern'], "regime": trade['regime'], "session": trade['session'],
                            "n": 0, "wins": 0, "total_r": 0.0, "weighted_n": 0.0, "weighted_wins": 0.0, "weighted_r": 0.0}
            
            raw[key]["n"] += 1
            raw[key]["total_r"] += trade["r_multiple"]
            if trade["outcome"] == "WIN":
                raw[key]["wins"] += 1
            
            age_index = n_live - 1 - i
            weight = math.exp(-age_index / 500.0)
            raw[key]["weighted_n"] += weight
            raw[key]["weighted_r"] += trade["r_multiple"] * weight
            if trade["outcome"] == "WIN":
                raw[key]["weighted_wins"] += weight
                
        self.matrix = {k: ExpectancyData(**v) for k, v in raw.items()}
        return self.matrix

async def run_audit():
    print("--- Phase 5: Bayesian Warm-Start Verification ---")
    prior_file = "scratch/priors/pattern_priors.json"
    matrix = ConditionalExpectancyMatrix(prior_file)
    
    # Test Case: Zero live trades - should only have priors
    matrix.build([])
    print(f"Matrix initialized with {len(matrix.matrix)} pattern-regime combinations from Priors.")
    
    bf_bull = matrix.matrix.get("BULL_FLAG|BULL|RTH")
    print(f"Verification [BULL_FLAG|BULL]: WR={bf_bull.win_rate:.1%}, n={bf_bull.n_trades} (Prior Only)")
    
    # Test Case: 1 Live Trade (LOSS) for BULL_FLAG|BULL
    matrix.build([{"pattern": "BULL_FLAG", "regime": "BULL", "session": "RTH", "outcome": "LOSS", "r_multiple": -1.0}])
    bf_bull_live = matrix.matrix.get("BULL_FLAG|BULL|RTH")
    print(f"Verification [BULL_FLAG|BULL] + 1 Loss: WR={bf_bull_live.win_rate:.1%}, n={bf_bull_live.n_trades}")
    
    if bf_bull_live.win_rate < bf_bull.win_rate:
        print("PASS: Live loss successfully decayed the prior.")
    else:
        print("FAIL: Win rate did not adjust.")

    print("\n--- Phase 5: Dynamic Hurdle Logic Audit ---")
    # Mocking Agent A logic
    atr = 4.0
    entry_comms = 2.0
    exit_comms = 2.0
    slippage = 0.5 # Simplified
    dynamic_hurdle = (2.0 * atr) + (entry_comms + exit_comms + slippage)
    print(f"Computed Dynamic Hurdle: ${dynamic_hurdle:.2f}")
    
    profit_low = 8.0
    profit_high = 15.0
    
    print(f"Trade A ($8.00 profit): {'FAIL' if profit_low < dynamic_hurdle else 'PASS'}")
    print(f"Trade B ($15.00 profit): {'PASS' if profit_high > dynamic_hurdle else 'FAIL'}")

if __name__ == "__main__":
    asyncio.run(run_audit())
