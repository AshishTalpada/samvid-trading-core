
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Mock objects to simulate the environment
class MockRegimeClassifier:
    def classify(self, vix, spy_above_200ma, breadth, momentum):
        if spy_above_200ma:
            return "BULLISH" if momentum > 0 else "CHOPPY_BULL"
        else:
            return "BEARISH" if momentum < 0 else "CHOPPY_BEAR"

async def reproduce_gap18():
    print("--- GAP-18 Reproduction: 24-hour news bias ---")
    
    # 1. Simulate 200 bars of 1m data (about 3 hours)
    # The reality is the market is in a 200-day DOWNTREND, 
    # but the last 3 hours show a small bounce.
    
    # Macro context (hidden from the current logic)
    daily_sma_200 = 500.0
    current_price = 480.0 # Price is BELOW daily SMA 200 (BEARISH REGIME)
    
    # Local window (what the brain sees)
    # Price bounced from 475 to 480 in the last 200 minutes.
    minutes = np.arange(200)
    prices = np.linspace(475, 480, 200) + np.random.normal(0, 0.1, 200)
    
    spy_df = pd.DataFrame({
        "close": prices,
        "timestamp": [datetime.now() - timedelta(minutes=int(200-i)) for i in range(200)]
    })
    
    print(f"Current Price: {current_price:.2f}")
    print(f"Actual Daily SMA 200: {daily_sma_200:.2f} (Price is BELOW -> Bearish)")

    # Current flawed logic:
    # sma_200 = spy_df["close"].mean()
    # spy_above_200ma = float(spy_df["close"].iloc[0]) > sma_200
    
    # Wait, the logic in brain.py line 2047:
    # sma_200 = spy_df["close"].mean()
    # spy_above_200ma = float(spy_df["close"].iloc[0]) > sma_200 
    # (Actually it compares the FIRST bar of the 200 bars with the mean of the 200 bars)
    
    local_mean = spy_df["close"].mean()
    first_bar = float(spy_df["close"].iloc[0])
    last_bar = float(spy_df["close"].iloc[-1])
    
    # In the code: spy_above_200ma = float(spy_df["close"].iloc[0]) > sma_200
    # This is even weirder. It's comparing the price 3 hours ago with the 3-hour mean.
    
    locally_bullish = last_bar > local_mean
    
    print(f"Local 3-hour Mean: {local_mean:.2f}")
    print(f"Brain Verdict (Local): {'BULLISH' if locally_bullish else 'BEARISH'} (WRONG context)")
    
    if locally_bullish and current_price < daily_sma_200:
        print("❌ CONFIRMED: Brain detects BULLISH regime during a MACRO BEARISH trend.")
        print("   This causes Agent A to take 'Bull Flags' into a daily wall of resistance.")

if __name__ == "__main__":
    asyncio.run(reproduce_gap18())
