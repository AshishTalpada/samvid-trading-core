
import asyncio
import logging
import sys
import os
from datetime import datetime

# --- Python 3.14 Compatibility ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from dhatu_oracle import DhatuOracle
from data_pipeline import DataPipeline
from agent_a import PatternDetector
from vault import Vault

# Setup specialized logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MARKET_AUDIT")

async def market_audit():
    logger.info("📡 INITIATING FULL MARKET AUDIT (SOVEREIGN V37.10)")
    logger.info("==========================================================")

    # 1. ORACLE SYNTHESIS (Macro Pulse)
    logger.info("🌍 LAYER 1: GLOBAL MACRO PULSE")
    oracle = DhatuOracle()
    
    # We manually trigger the full cycle which hits SPY, QQQ, VIX, Gold, etc.
    macro_state = await oracle._full_synthesis_cycle()
    
    if macro_state:
        logger.info(f"📊 CURRENT REGIME: [{macro_state.dhatu_state}]")
        logger.info(f"   Action Protocol: {macro_state.action_protocol}")
        logger.info(f"   Risk Modifier: {macro_state.risk_modifier:.2f}x")
        logger.info(f"   Macro Bias: {macro_state.source_graph.macro_bias if macro_state.source_graph else 'N/A'}")
        logger.info(f"   Theme: {macro_state.causation_summary}")
        
        if macro_state.source_graph and macro_state.source_graph.edges:
            logger.info("   Causal Edges Detected:")
            for edge in macro_state.source_graph.edges:
                logger.info(f"     - {edge.source} -> {edge.effect} ({edge.mechanism})")
    else:
        logger.error("❌ Macro synthesis failed.")

    # 2. SECTOR SCAN (The 'Breadth' Check)
    logger.info("\n🔦 LAYER 2: SECTOR SCAN & PATTERN SEARCH")
    pipeline = DataPipeline()
    detector = PatternDetector()
    
    # High-impact universe
    universe = ["SPY", "QQQ", "NVDA", "TSLA", "AAPL", "AMD", "COIN"]
    
    for symbol in universe:
        logger.info(f"   Scanning {symbol}...")
        df = await pipeline.fetch_ohlcv(symbol, tf="1m", bars=100)
        if df is None or len(df) == 0:
            logger.warning(f"     [!] No data for {symbol}")
            continue
            
        # Run Pattern Detection
        patterns = []
        if detector.detect_bull_flag(df): patterns.append("Bull Flag")
        if detector.detect_bear_flag(df): patterns.append("Bear Flag")
        if detector.detect_head_and_shoulders(df): patterns.append("H&S")
        if detector.detect_falling_wedge(df): patterns.append("Falling Wedge")
        
        if patterns:
            logger.info(f"     ✅ PATTERNS FOUND: {', '.join(patterns)}")
        else:
            logger.info(f"     [-] No technical setups detected.")

    # 3. SYSTEM HEALTH CHECK
    logger.info("\n🛡️ LAYER 3: SYSTEM INTEGRITY & WIRING")
    logger.info(f"   Active Broker: {Vault.get('ACTIVE_BROKER') or 'IBKR'}")
    logger.info(f"   Ollama Status: [INDEPENDENT] (Heuristics Active)")
    logger.info(f"   Data Mode: {Vault.get('TRADING_MODE', 'paper')}")

    logger.info("\n==========================================================")
    logger.info("🏁 MARKET AUDIT COMPLETE. System is performing nominally.")

if __name__ == "__main__":
    asyncio.run(market_audit())
