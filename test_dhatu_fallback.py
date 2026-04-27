import asyncio
import logging
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

from src.dhatu_oracle import DhatuOracle, CausationGraph  # type: ignore
from src.vault import Vault  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from unittest.mock import AsyncMock, patch

# GAP-129 FIX: Mock ingestion to prevent provider hangs (OpenBB SDK load)
@patch("src.dhatu_oracle.DhatuOracle._ingest_macro", new_callable=AsyncMock)
async def test_fallback_chain(mock_ingest):
    mock_ingest.return_value = ["MOCK DATA"]
    
    # 1. Initialize with NO keys to force Rule-Based Fallback
    logger.info("--- Testing Phase 1: Rule-Based Fallback (No Keys) ---")
    oracle = DhatuOracle(google_api_key="", anthropic_api_key="")
    
    # Mock some bearish signals
    signals = [
        "VIX (^VIX): 24.50 (change: +18.20%)",
        "S&P 500 Large Cap (SPY): 502.11 (change: -2.30%)",
        "Gold Futures (GC=F): 2150.00 (change: +1.50%)",
        "10-Year Treasury Yield (^TNX): 4.10 (change: -3.20%)"
    ]
    
    state = await oracle._map_to_dhatu_state(
        graph=CausationGraph(dominant_theme="TEST_MOCK"),
        all_signals=signals
    )
    
    # GAP-131 FIX: Precise state assertion instead of broad membership
    # With VIX 24.50 and SPY -2.3%, it should be 'Abhava' (Systemic Shock)
    assert state.dhatu_state == "Abhava", f"Expected 'Abhava' for shock signals, got {state.dhatu_state}"
    
    # GAP-130 FIX: Use regex or case-insensitive checks to reduce fragility
    import re
    assert re.search(r"VIX.*Absolute", state.causation_summary, re.IGNORECASE), "Reasoning should reflect VIX absolute logic"
    logger.info("✓ Rule-Based Fallback Verified")

    # 2. Test Absolute Value Sensitivity (GAP-132 / GAP-80 FIX)
    logger.info("--- Testing Phase 3: Absolute Value Sensitivity ---")
    # VIX is HIGH (45) but DROPPING (-5%)
    mock_signals = [
        "VIX (^VIX): 45.00 (change: -5.00%)",
        "S&P 500 Large Cap (SPY): 480.00 (change: +0.50%)" 
    ]
    
    crisis_state = await oracle._map_to_dhatu_state(
        graph=CausationGraph(dominant_theme="LATENT_CRISIS"),
        all_signals=mock_signals
    )
    
    # GAP-132: Ensure high VIX triggers Abhava even if momentum is negative
    assert crisis_state.dhatu_state == "Abhava", "High VIX (45) MUST trigger Abhava regardless of sign"
    logger.info("✓ Absolute Value Sensitivity Verified")

if __name__ == "__main__":
    asyncio.run(test_fallback_chain())
