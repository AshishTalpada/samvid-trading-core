
import asyncio
import json
import logging
import sys
from pathlib import Path
import math

# Use the actual classes if possible, but for a standalone test we can simulate
# Alternatively, we can import them. Since we are in the workspace, let's try to import.
sys.path.append(str(Path(__file__).parent.parent / "src"))
from agent_d import ConditionalExpectancyMatrix, ExpectancyData

async def test_evolution_pipeline():
    print("--- Phase 6: Evolutionary Persistence Bootstrapper ---")
    
    # 1. Clean up old dynamic priors for a clean test
    dynamic_path = Path("scratch/priors/dynamic_priors.json")
    if dynamic_path.exists():
        dynamic_path.unlink()
        print("Cleaned existing dynamic_priors.json")

    matrix = ConditionalExpectancyMatrix()
    
    # 2. Simulate 50 trades to trigger a persistence check
    # In agent_d.py, the save is triggered by the LiveLearningEngine.
    # Here we test the save_priors method directly first.
    
    print("Simulating 51 trades for BULL_FLAG...")
    mock_history = []
    for i in range(51):
        mock_history.append({
            "pattern": "BULL_FLAG",
            "regime": "BULL",
            "session": "RTH",
            "outcome": "WIN" if i % 2 == 0 else "LOSS",
            "r_multiple": 2.5 if i % 2 == 0 else -1.0
        })
    
    matrix.build(mock_history)
    matrix.save_priors()
    
    if dynamic_path.exists():
        print(f"SUCCESS: {dynamic_path} created.")
        data = json.loads(dynamic_path.read_text())
        bf_stats = data.get("BULL_FLAG", {}).get("BULL", {})
        print(f"Saved Stats: n={bf_stats.get('n')}, WR={bf_stats.get('win_rate')}")
        
        # 3. Reload Check
        print("\nVerifying Reload Hierarchy (Dynamic > Static)...")
        new_matrix = ConditionalExpectancyMatrix()
        # The log should say "Dynamic (Evolutionary) Priors loaded"
        # We check the memory values
        if new_matrix.priors.get("BULL_FLAG", {}).get("BULL", {}).get("n") > 500:
            print("PASS: System reloaded from Dynamic Priors (Historical n=500, Dynamic n=551).")
        else:
            print("FAIL: System reloaded from Static Priors.")
    else:
        print("FAIL: dynamic_priors.json was not created.")

if __name__ == "__main__":
    asyncio.run(test_evolution_pipeline())
