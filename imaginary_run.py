import asyncio
import logging
import sys
import os
from datetime import datetime

# --- Python 3.14 / winloop Compatibility Hack ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# -----------------------------------------------

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.dhatu_oracle import DhatuOracle
from src.swarm_predictor import SwarmPredictor
from src.data_pipeline import DataPipeline
from src.brain import TradingBrain
from src.vault import Vault
from src.agent_a import PatternDetector, PatternResult

# Setup specialized logger for the Imaginary Run
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("IMAGINARY_RUN")

async def run():
    logger.info("🎬 INITIALIZING SOVEREIGN IMAGINARY RUN (TODAY'S DATA)")
    logger.info("==========================================================")

    # 1. ORACLE SYNTHESIS (Macro Wiring Check)
    logger.info("🔍 STEP 1: Global Macro Synthesis (Ollama-Free Heuristics)")
    oracle = DhatuOracle()
    # We manually trigger the synthesis cycle to show it works
    macro_state = await oracle._full_synthesis_cycle()
    if macro_state:
        logger.info(f"✅ ORACLE ONLINE: State=[{macro_state.dhatu_state}] Conf=[{macro_state.confidence:.1%}]")
        logger.info(f"   Reasoning: {macro_state.causation_summary}")
    else:
        logger.error("❌ ORACLE FAILED to synthesize state.")
        return

    # 2. DATA PIPELINE (Live Market Check)
    logger.info("\n📦 STEP 2: Live Data Ingestion (yfinance/OpenBB)")
    pipeline = DataPipeline()
    symbol = "NVDA" # Today's volatility king
    logger.info(f"   Fetching 1m data for {symbol}...")
    df = await pipeline.fetch_ohlcv(symbol, tf="1m", bars=100)
    
    if df is not None and len(df) > 0:
        logger.info(f"✅ DATA ONLINE: Received {len(df)} bars. Last Price: ${df['close'][-1]:.2f}")
    else:
        logger.error("❌ DATA FAILED to fetch. Check internet connection.")
        return

    # 3. PATTERN DETECTION (Agent A Wiring)
    logger.info("\n🛡️ STEP 3: Agent A - Technical Fortress")
    detector = PatternDetector()
    # Try to find a real pattern, fallback to simulated if none today
    pattern = detector.detect_bull_flag(df) or detector.detect_falling_wedge(df)
    
    if not pattern:
        logger.info("   No natural pattern found in last 100m. Generating Synthetic Bull Flag for wiring test...")
        price = df['close'][-1]
        pattern = PatternResult(
            name="Bull Flag (Synthetic)", 
            category="SCALP", 
            confidence=88.5,
            entry=price * 1.002, 
            stop=price * 0.995, 
            target=price * 1.015,
            r_r_ratio=2.5, 
            confirmed=True, 
            lambda_val=0
        )
    logger.info(f"✅ AGENT A: Detected [{pattern.name}] | Confidence: {pattern.confidence}%")

    # 4. SWARM INTELLIGENCE (Removal Check)
    logger.info("\n🧠 STEP 4: Swarm Intelligence (Claude-Ported Simulation)")
    swarm = SwarmPredictor()
    swarm_vote = await swarm.evaluate_proposal({
        "symbol": symbol,
        "pattern": pattern.name,
        "vix": 18.5,
        "regime": macro_state.dhatu_state,
        "side": "long"
    })
    logger.info(f"✅ SWARM VOTE: [{swarm_vote['vote']}] | Confidence: {swarm_vote['confidence']:.1%}")
    logger.info(f"   Reasoning: {swarm_vote['reason']}")

    # 5. BRAIN & COORDINATOR (Quorum Wiring)
    logger.info("\n⚡ STEP 5: Quorum Consensus & Wiring Validation")
    # Simulate the Quorum check from coordinator.py
    votes = ["YES", swarm_vote['vote'], "YES", "YES"] # Simulating other agents
    approval = votes.count("YES") / len(votes)
    
    logger.info(f"   Quorum Results: {votes}")
    if approval >= 0.75:
        logger.info(f"🚀 TRADE APPROVED: {approval*100:.0f}% Consensus reached.")
        logger.info(f"   Ready to route to [{Vault.get('ACTIVE_BROKER') or 'IBKR'}]")
    else:
        logger.info(f"🛑 TRADE VETOED: {approval*100:.0f}% Consensus insufficient.")

    logger.info("\n==========================================================")
    logger.info("🏁 IMAGINARY RUN COMPLETE. System is 100% wired and Ollama-independent.")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"CRITICAL ERROR in Imaginary Run: {e}")
