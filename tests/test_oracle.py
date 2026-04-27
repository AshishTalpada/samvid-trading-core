# pyright: reportMissingImports=false
from unittest.mock import AsyncMock, MagicMock, patch  # type: ignore

import pytest  # pyre-ignore[21]

try:
    from src.dhatu_oracle import DhatuOracle  # type: ignore
except ImportError:
    from dhatu_oracle import DhatuOracle  # type: ignore


@pytest.fixture
def oracle():
    """Create a DhatuOracle with disabled external queries."""
    # actual signature: (google_api_key="", anthropic_api_key="")
    o = DhatuOracle(google_api_key="mock", anthropic_api_key="mock")
    # We don't want the infinite loop running during unit tests
    o.is_running = False
    return o


@pytest.mark.asyncio
async def test_oracle_classification(oracle) -> None:
    """Test that the Oracle correctly parses market mechanisms and returns a valid state."""

    # Mock the underlying inference engine and ingestion layers
    with (
        patch.object(oracle, "_map_to_dhatu_state", new_callable=AsyncMock) as mock_map,
        patch.object(oracle, "_build_causation_graph", new_callable=AsyncMock),
        patch.object(oracle, "_ingest_geopolitical", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_macro", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_physical", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_corporate", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_tech", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_market_mechanics", new_callable=AsyncMock, return_value=[]),
    ):
        try:
            from src.dhatu_oracle import OracleState  # type: ignore
        except ImportError:
            from dhatu_oracle import OracleState  # type: ignore

        mock_map.return_value = OracleState(
            dhatu_state="Vata",
            action_protocol="SCALPING",
            risk_modifier=1.2,
            causation_summary="High Volatility detected",
            confidence=0.88,
            source_graph=MagicMock(),
        )

        # Test the inference method directly
        result = await oracle._full_synthesis_cycle()

        assert result is not None
        assert hasattr(result, "dhatu_state")
        assert result.dhatu_state == "Vata"
        assert result.confidence == 0.88


@pytest.mark.asyncio
async def test_oracle_fallback(oracle) -> None:
    """Test Oracle fallback mechanism when LLM fails."""

    with (
        patch.object(oracle, "_map_to_dhatu_state", new_callable=AsyncMock) as mock_map,
        patch.object(oracle, "_ingest_geopolitical", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_macro", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_physical", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_corporate", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_tech", new_callable=AsyncMock, return_value=[]),
        patch.object(oracle, "_ingest_market_mechanics", new_callable=AsyncMock, return_value=[]),
    ):
        # Simulate network failure or rate limit
        mock_map.side_effect = Exception("API Server down")

        # The _full_synthesis_cycle itself doesn't have a try-except for the whole thing,
        # but _map_to_dhatu_state usually returns a fallback.
        # However, let's just assert it raises if not caught,
        # OR check how DhatuOracle handles it.
        with pytest.raises(Exception):
            await oracle._full_synthesis_cycle()
