# pyre-ignore-all-errors[21]
"""
tests/test_swarm_predictor.py — Unit tests for SwarmPredictor

Tests graceful degradation, consensus parsing, and blocking/modifier logic.
"""

from unittest.mock import patch  # pyre-ignore[21]

import pytest  # pyre-ignore[21]

# ── Test: Data Models ─────────────────────────────────────────────────


def test_swarm_bias_enum() -> None:
    """SwarmBias should have BULLISH, BEARISH, NEUTRAL values."""
    from src.swarm_predictor import SwarmBias  # type: ignore

    assert SwarmBias.BULLISH.value == "BULLISH"
    assert SwarmBias.BEARISH.value == "BEARISH"
    assert SwarmBias.NEUTRAL.value == "NEUTRAL"


def test_swarm_consensus_defaults() -> None:
    """SwarmConsensus should default to NEUTRAL with 0 confidence."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus()
    assert c.bias == SwarmBias.NEUTRAL
    assert c.confidence == 0.0
    assert c.agent_count == 0
    assert c.is_fresh is False


def test_should_block_entry_bearish_vs_long() -> None:
    """High-confidence BEARISH consensus should block long entries."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus(bias=SwarmBias.BEARISH, confidence=0.80)
    assert c.should_block_entry("long") is True
    assert c.should_block_entry("short") is False


def test_should_block_entry_bullish_vs_short() -> None:
    """High-confidence BULLISH consensus should block short entries."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus(bias=SwarmBias.BULLISH, confidence=0.85)
    assert c.should_block_entry("short") is True
    assert c.should_block_entry("long") is False


def test_should_not_block_low_confidence() -> None:
    """Low confidence swarm should never block entries."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus(bias=SwarmBias.BEARISH, confidence=0.50)
    assert c.should_block_entry("long") is False
    assert c.should_block_entry("short") is False


def test_confidence_modifier_neutral() -> None:
    """NEUTRAL bias should return 1.0 modifier (no effect)."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus(bias=SwarmBias.NEUTRAL, confidence=0.80)
    assert c.get_confidence_modifier() == 1.0


def test_confidence_modifier_high_confidence() -> None:
    """High-confidence aligned bias should return > 1.0 modifier."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus(bias=SwarmBias.BULLISH, confidence=0.90)
    modifier = c.get_confidence_modifier()
    assert modifier > 1.0
    assert modifier <= 1.15


def test_confidence_modifier_low_confidence() -> None:
    """Low-confidence should return 1.0 modifier (no effect)."""
    from src.swarm_predictor import SwarmBias, SwarmConsensus  # type: ignore

    c = SwarmConsensus(bias=SwarmBias.BULLISH, confidence=0.30)
    assert c.get_confidence_modifier() == 1.0


# ── Test: SwarmPredictor Initialization ───────────────────────────────


def test_predictor_initializes() -> None:
    """SwarmPredictor should initialize without error and be unavailable without API key."""
    from src.swarm_predictor import SwarmPredictor  # type: ignore

    # Patch Vault so no local LLM and no OPENAI key is found
    def mock_vault_get(key, default=None):
        if key == "USE_LOCAL_LLM":
            return "false"
        if key == "OPENAI_API_KEY":
            return None
        return default

    # Patch Vault both ways (src.vault and vault) to catch all import variations
    with (
        patch("src.vault.Vault.get", side_effect=mock_vault_get),
        patch("vault.Vault.get", side_effect=mock_vault_get, create=True),
    ):
        p = SwarmPredictor(api_url="http://localhost:5001")
        try:
            assert p is not None
            assert p.is_available is False  # Explicitly disabled -> unavailable
        finally:
            p.stop()


def test_predictor_custom_url() -> None:
    """SwarmPredictor should accept custom API URL."""
    from src.swarm_predictor import SwarmPredictor  # type: ignore

    p = SwarmPredictor(api_url="http://example.com:9000")
    assert "example.com" in p._api_url


# ── Test: Graceful Degradation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_forecast_returns_neutral_when_unavailable(ticker) -> None:
    """get_market_forecast should return NEUTRAL when predictor has no API key."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    def mock_vault_get(key, default=None):
        if key == "USE_LOCAL_LLM":
            return "false"
        if key == "OPENAI_API_KEY":
            return None
        return default

    # Force unavailable by patching Vault both ways
    with (
        patch("src.vault.Vault.get", side_effect=mock_vault_get),
        patch("vault.Vault.get", side_effect=mock_vault_get, create=True),
    ):
        p = SwarmPredictor(api_url="http://localhost:59999")

    result = await p.get_market_forecast(
        symbol=ticker,
        context={"price": 500.0, "regime": "NORMAL"},
    )
    assert result.bias == SwarmBias.NEUTRAL
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_get_consensus_returns_neutral_initially() -> None:
    """get_swarm_consensus should return NEUTRAL when no prediction computed."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    p = SwarmPredictor()
    result = await p.get_swarm_consensus()
    assert result.bias == SwarmBias.NEUTRAL


# ── Test: Prediction Parsing ──────────────────────────────────────────


def test_parse_bullish_prediction() -> None:
    """_parse_prediction should detect BULLISH from report text."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    p = SwarmPredictor()
    data = {
        "report": "The market shows bullish momentum with strong rally potential.",
        "confidence": 0.75,
        "agent_count": 100,
        "rounds": 40,
    }
    result = p._parse_prediction(data)
    assert result.bias == SwarmBias.BULLISH
    assert result.confidence == 0.75
    assert result.agent_count == 100


def test_parse_bearish_prediction() -> None:
    """_parse_prediction should detect BEARISH from report text."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    p = SwarmPredictor()
    data = {
        "report": "Clear bearish decline expected across major indices.",
        "confidence": 0.82,
        "agent_count": 200,
        "rounds": 30,
    }
    result = p._parse_prediction(data)
    assert result.bias == SwarmBias.BEARISH
    assert result.confidence == 0.82


def test_parse_neutral_prediction() -> None:
    """_parse_prediction should return NEUTRAL for ambiguous text."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    p = SwarmPredictor()
    data = {
        "report": "Market conditions are mixed with no clear direction.",
        "confidence": 0.45,
        "agent_count": 50,
        "rounds": 20,
    }
    result = p._parse_prediction(data)
    assert result.bias == SwarmBias.NEUTRAL


def test_parse_dict_report() -> None:
    """_parse_prediction should handle dict-format reports."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    p = SwarmPredictor()
    data = {
        "report": {"summary": "Strong upward rally expected.", "text": ""},
        "confidence": 0.88,
        "agent_count": 150,
        "rounds": 40,
    }
    result = p._parse_prediction(data)
    assert result.bias == SwarmBias.BULLISH
    assert result.confidence == 0.88


def test_confidence_clamping() -> None:
    """Confidence should be clamped to [0.0, 1.0]."""
    from src.swarm_predictor import SwarmPredictor  # type: ignore

    p = SwarmPredictor()
    data = {"report": "test", "confidence": 1.5}
    result = p._parse_prediction(data)
    assert result.confidence == 1.0

    data2 = {"report": "test", "confidence": -0.5}
    result2 = p._parse_prediction(data2)
    assert result2.confidence == 0.0


def test_neutral_consensus_helper() -> None:
    """_neutral_consensus should return a NEUTRAL SwarmConsensus."""
    from src.swarm_predictor import SwarmBias, SwarmPredictor  # type: ignore

    c = SwarmPredictor._neutral_consensus("Test reason")
    assert c.bias == SwarmBias.NEUTRAL
    assert c.confidence == 0.0
    assert c.summary == "Test reason"
    assert c.is_fresh is False
