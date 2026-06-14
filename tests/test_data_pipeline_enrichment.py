from unittest.mock import AsyncMock

import pytest

from data_pipeline import DataPipeline


def _pipeline_without_init() -> DataPipeline:
    return object.__new__(DataPipeline)


@pytest.mark.asyncio
async def test_macro_stress_uses_brain_compatible_bearish_contract() -> None:
    pipeline = _pipeline_without_init()
    pipeline.fetch_macro_snapshot = AsyncMock(
        return_value={"vix": 31.0, "treasury_10y": 4.2, "dxy": 102.0}
    )

    result = await pipeline.fetch_macro_impact()

    assert result["impact"] == "BEARISH"
    assert result["regime"] == "HEDGING"
    assert result["status"] == "ONLINE"


@pytest.mark.asyncio
async def test_macro_unavailable_does_not_invent_neutral_metrics() -> None:
    pipeline = _pipeline_without_init()
    pipeline.fetch_macro_snapshot = AsyncMock(return_value={})

    result = await pipeline.fetch_macro_impact()

    assert result["impact"] == "UNKNOWN"
    assert result["status"] == "UNAVAILABLE"
    assert "metrics" not in result


@pytest.mark.asyncio
async def test_unconfigured_research_feeds_do_not_return_fake_events() -> None:
    pipeline = _pipeline_without_init()

    assert await pipeline.fetch_dark_pool_logic("SPY") == "UNAVAILABLE"
    assert await pipeline.fetch_fomc_calendar() == []
