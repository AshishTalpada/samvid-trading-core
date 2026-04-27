import asyncio
import json
import logging
from datetime import datetime

# Import components directly for a clean "bypass" test
from src.coordinator import TradingCoordinator
from src.mind_bridge import MindBridge
from src.intelligence_bus import SharedIntelligenceBus
from src.brain import TradingBrain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PulseTest")

async def run_pulse():
    bus = SharedIntelligenceBus()
    await bus.start()
    
    # We need a brain instance but we don't want to run its full loop
    # We just want to use its internal state for the coordinator
    brain = TradingBrain(bus=bus)
    
    # PULSE TRIGGER: A perfect NVDA setup
    # RR = (150-120)/(120-110) = 3.0
    # Confidence = 85.0
    signal = {
        "symbol": "NVDA",
        "pattern": {
            "name": "Synthetic Hyper-Growth Breakout",
            "entry": 120.0,
            "stop": 110.0,
            "target": 150.0,
            "confidence": 85.0,
            "lambda_val": 25.0,
            "r_r_ratio": 3.0
        },
        "reason": "Synthetic Perfect Setup for Pulse Validation"
    }
    
    logger.info("🚀 MANUALLY INITIATING LIFECYCLE FOR PERFECT SIGNAL...")
    # This will trigger the actual Coordinator.initiate_trade_lifecycle
    # It will use the real Reasoning (Ultrathink), real Sizing, real Guards, and Telegram.
    success = await brain.coordinator.initiate_trade_lifecycle("NVDA", signal)
    
    if success:
        logger.info("✅ PULSE TEST SUCCESSFUL: Lifecycle completed and notification sent.")
    else:
        logger.error("❌ PULSE TEST FAILED: Lifecycle was vetoed.")

if __name__ == "__main__":
    asyncio.run(run_pulse())
