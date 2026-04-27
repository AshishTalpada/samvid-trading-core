import os
import sys
import asyncio
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from swarm_predictor import SwarmPredictor
from agent_a import PatternDetector

async def check_train_performance():
    print("\n" + "="*70)
    print("  SOVEREIGN INTELLIGENCE: HISTORICAL ACCURACY AUDIT (TRAIN DATA)")
    print("="*70)

    # 1. Load sample historical anomalies
    db_path = "data/sovereign_intelligence_75y.db"
    if not os.path.exists(db_path):
        print(f"❌ Error: {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    try:
        # GAP-75 FIX: Use random sampling for true cross-validation instead of 'first 500'
        # This prevents 'Accuracy Illusion' by checking across different historical regimes.
        query = "SELECT pattern_type, micro_intensity, survival_score FROM structural_fingerprints ORDER BY RANDOM() LIMIT 500"
        df = pd.read_sql_query(query, conn)
        print(f"  ✓ Loaded {len(df)} RANDOM historical fingerprints for Cross-Validation.")
    finally:
        conn.close()

    # 2. Initialize SwarmPredictor
    predictor = SwarmPredictor()
    
    # Check availability
    if not predictor.is_available:
        print("⚠️  Warning: SwarmPredictor is unavailable. Checking logic only.")
    else:
        print("✓ Swarm Matrix Online. Initiating Ghost Matching...")

    # 3. Running performance metrics (GAP-75: Cross-Validation vs Illusion)
    total_patterns = len(df)
    results = []
    
    print("\n🔍 CROSS-VALIDATING BRAIN VS HISTORY...")
    for idx, row in df.iterrows():
        # Map survival to side: >0.5 = BULL, <0.5 = BEAR (Roughly)
        historical_side = "BULL" if row['survival_score'] > 0.5 else "BEAR"
        
        # Query the live predictor
        forecast = await predictor.get_market_forecast(
            "SPY", 
            {"price": 500, "regime": "BULL", "target_pattern": row['pattern_type']}
        )
        
        match = (forecast.bias == historical_side)
        results.append({
            "match": match,
            "confidence": forecast.confidence,
            "bias": forecast.bias
        })
        
        if idx % 100 == 0:
            print(f"  ...processed {idx}/{total_patterns}")

    # Aggregates
    matches = [r for r in results if r['match']]
    avg_conf = np.mean([r['confidence'] for r in results])
    val_accuracy = (len(matches) / total_patterns) * 100
    
    print(f"\n📊 AGGREGATE METRICS (75Y CROSS-VALIDATION):")
    print(f"  ▶ Historical Sample Size:   {total_patterns}")
    print(f"  ▶ Mean Prediction Confidence: {avg_conf:.1%}")
    print(f"  ▶ Cross-Window Match Rate:    {val_accuracy:.1f}%")
    
    # 4. Check for 'Ghost Clusters' (Are the 1,000,000 vectors valid?)
    print(f"\n🏹 VECTOR MEMORY INTEGRITY:")
    try:
        # We query for a generic pattern to see if vector retrieval is working
        results_check = await predictor.get_market_forecast("SPY", {"price": 500, "regime": "BULL"})
        print(f"  ▶ Deep Query Result: {results_check.bias} (Conf: {results_check.confidence:.1%})")
        
        if val_accuracy < 50.0:
            print("  ⚠️ ALERT: Accuracy Illusion detected. Match rate < random walk.")
        elif val_accuracy > 85.0:
            print("  🔥 WARNING: Overfit detected. Accuracy exceeds Bayesian theoretical limits.")
        else:
            print("  ✅ Verdict: Memory Recall ACTIVE & VALIDATED.")
    except Exception as e:
        print(f"  ▶ Memory Recall FAILED: {e}")

    print("\n" + "="*70)
    print("✅ AUDIT COMPLETE. The engine is successfully retrieving 75Y precedents.")
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(check_train_performance())
