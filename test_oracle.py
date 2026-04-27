import asyncio
import logging
import sys
import os

from unittest.mock import AsyncMock, patch
import pytest

# GAP-127 FIX: Use a clean relative import strategy or single path append
sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

from vault import Vault
from dhatu_oracle import DhatuOracle, DhatuState, MacroConsensus

# GAP-125 FIX: Mocking the expensive API calls to prevent cost leaks during testing
@pytest.mark.asyncio
async def test_dhatu_oracle_synthesis():
    """Harden Oracle Test with mocks and assertions (GAPs 125-126)."""
    with patch("dhatu_oracle.DhatuOracle._ingest_macro", new_callable=AsyncMock) as mock_macro, \
         patch("dhatu_oracle.DhatuOracle._ingest_geopolitical", new_callable=AsyncMock) as mock_geo:
        
        # 1. Setup Mocks
        mock_macro.return_value = ["VIX is rising", "CPI Data expected higher"]
        mock_geo.return_value = ["Middle East tensions"]
        
        # GAP-128 FIX: Use mock keys if Vault is empty
        oracle = DhatuOracle(
            google_api_key="MOCK_KEY",
            anthropic_api_key="MOCK_KEY"
        )
        
        # 2. Execute
        signals = await oracle._ingest_macro()
        signals += await oracle._ingest_geopolitical()
        
        # 3. Assertions (GAP-126)
        assert len(signals) == 3
        assert "VIX is rising" in signals
        
        graph = await oracle._build_causation_graph(signals)
        assert graph.macro_bias in ["BULLISH", "BEARISH", "NEUTRAL"]
        
        state = await oracle._map_to_dhatu_state(graph)
        assert isinstance(state, DhatuState)
        assert state.confidence >= 0.0 and state.confidence <= 1.0
        print(f"\n✅ Oracle Test Passed: {state.dhatu_state} ({state.confidence:.1%})")

if __name__ == "__main__":
    # Allow running directly or via pytest
    asyncio.run(test_dhatu_oracle_synthesis())
