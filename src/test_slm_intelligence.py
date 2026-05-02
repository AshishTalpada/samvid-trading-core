import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from native_slm import NativeSLM

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("SLM_Test")

async def test_scenarios():
    print("\n" + "="*50)
    print("🚀 SOVEREIGN SLM INTELLIGENCE AUDIT")
    print("="*50)
    
    slm = NativeSLM()
    if not slm.is_available:
        print("❌ Error: SLM not available.")
        return

    scenarios = [
        {
            "name": "🔥 SCENARIO 1: AGGRESSIVE BULLISH (The Vriddhi State)",
            "context": {
                "symbol": "BTCUSD",
                "regime": "Strong Uptrend",
                "dhatu_state": "Vriddhi (Growth)",
                "pattern": "Bull Flag Breakout",
                "catalyst_score": 0.95,
                "belief": 0.9,
                "side": "long"
            }
        },
        {
            "name": "❄️ SCENARIO 2: BEARISH DECAY (The Kshaya State)",
            "context": {
                "symbol": "SPY",
                "regime": "Distribution / Downtrend",
                "dhatu_state": "Kshaya (Decay)",
                "pattern": "Head and Shoulders",
                "catalyst_score": 0.2,
                "belief": 0.1,
                "side": "short"
            }
        },
        {
            "name": "🚧 SCENARIO 3: CONTRADICTION VETO (Bullish Pattern in Bearish Dhatu)",
            "context": {
                "symbol": "EURUSD",
                "regime": "Bearish",
                "dhatu_state": "Viyoga (Separation/Fear)",
                "pattern": "Double Bottom",
                "catalyst_score": 0.4,
                "belief": 0.6,
                "side": "long"
            }
        },
        {
            "name": "🌪️ SCENARIO 4: UNCERTAINTY (The Chala State)",
            "context": {
                "symbol": "NVDA",
                "regime": "Sideways",
                "dhatu_state": "Chala (Volatile/Uncertain)",
                "pattern": "No Clear Pattern",
                "catalyst_score": 0.5,
                "belief": 0.5,
                "side": "long"
            }
        }
    ]

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"   Input -> {scenario['context']['symbol']} | {scenario['context']['regime']} | {scenario['context']['dhatu_state']}")
        
        result = await slm.evaluate_proposal(scenario['context'])
        
        vote_icon = "✅" if result['vote'] == "YES" else "❌"
        print(f"   SLM BIAS: {result['bias']}")
        print(f"   VOTE: {vote_icon} {result['vote']}")
        print(f"   REASON: {result['reason']}")
        print(f"   CONFIDENCE: {result['confidence']:.2f}")

    print("\n" + "="*50)
    print("🏁 AUDIT COMPLETE")
    print("="*50)
    await slm.close()

if __name__ == "__main__":
    asyncio.run(test_scenarios())
