# pyre-ignore-all-errors[21]
"""
tests/test_openbb_provider.py — Unit tests for OpenBBProvider

Tests graceful degradation, data structure correctness, and fallback behavior.
"""

import pytest  # pyre-ignore[21]

# ── Test: Initialization ─────────────────────────────────────────────


def test_openbb_provider_initializes_without_pat() -> None:
    """OpenBBProvider should initialize without a PAT token."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider(pat="", preferred_provider="yfinance")
    # Should not crash — may or may not be "available" depending on
    # whether the openbb package is installed in this test environment.
    assert provider is not None


def test_openbb_provider_initializes_with_pat() -> None:
    """OpenBBProvider should accept a PAT without crashing."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider(pat="fake_pat_token", preferred_provider="yfinance")
    assert provider is not None


@pytest.mark.asyncio
async def test_openbb_provider_is_available_property() -> None:
    """is_available should be False when openbb is not installed, True otherwise."""
    import src.openbb_provider as openbb_mod
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider(pat="")
    await provider.initialize()
    if openbb_mod._OPENBB_AVAILABLE:
        assert provider.is_available is True
    else:
        assert provider.is_available is False


# ── Test: Graceful Degradation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ohlcv_returns_none_when_unavailable() -> None:
    """fetch_ohlcv should return None when OpenBB is not available."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider.__new__(OpenBBProvider)
    provider._initialized = False
    provider._pat = ""
    provider._provider = "yfinance"

    result = await provider.fetch_ohlcv("SPY", period_days=30)
    assert result is None


@pytest.mark.asyncio
async def test_current_price_returns_none_when_unavailable() -> None:
    """get_current_price should return None when OpenBB is not available."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider.__new__(OpenBBProvider)
    provider._initialized = False
    provider._pat = ""
    provider._provider = "yfinance"

    result = await provider.get_current_price("SPY")
    assert result is None


@pytest.mark.asyncio
async def test_technical_indicators_returns_empty_when_unavailable() -> None:
    """fetch_technical_indicators should return empty dict when OpenBB is not available."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider.__new__(OpenBBProvider)
    provider._initialized = False
    provider._pat = ""
    provider._provider = "yfinance"

    result = await provider.fetch_technical_indicators("SPY")
    assert result == {}


@pytest.mark.asyncio
async def test_macro_data_returns_empty_when_unavailable() -> None:
    """fetch_macro_data should return empty dict when OpenBB is not available."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider.__new__(OpenBBProvider)
    provider._initialized = False
    provider._pat = ""
    provider._provider = "yfinance"

    result = await provider.fetch_macro_data()
    assert result == {}


@pytest.mark.asyncio
async def test_news_returns_empty_when_unavailable() -> None:
    """fetch_news should return empty list when OpenBB is not available."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider.__new__(OpenBBProvider)
    provider._initialized = False
    provider._pat = ""
    provider._provider = "yfinance"

    result = await provider.fetch_news("SPY")
    assert result == []


@pytest.mark.asyncio
async def test_crypto_returns_none_when_unavailable() -> None:
    """fetch_crypto_ohlcv should return None when OpenBB is not available."""
    from src.openbb_provider import OpenBBProvider  # type: ignore

    provider = OpenBBProvider.__new__(OpenBBProvider)
    provider._initialized = False
    provider._pat = ""
    provider._provider = "yfinance"

    result = await provider.fetch_crypto_ohlcv("BTCUSD")
    assert result is None
