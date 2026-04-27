# pyright: reportMissingImports=false
import pytest  # type: ignore

try:
    from src.brain import (  # type: ignore
        DrawdownLadder,
        DrawdownLevel,
    )
except ImportError:
    from brain import (  # type: ignore
        DrawdownLadder,
        DrawdownLevel,
    )


@pytest.fixture
def ladder():
    """Create a DrawdownLadder for an IBKR account."""
    return DrawdownLadder(account_type="ibkr", peak_equity=100000.0)


def test_drawdown_ladder_normal(ladder) -> None:
    """Test that drawdown is NORMAL at 100k equity."""
    level = ladder.update(100000.0)
    assert level == DrawdownLevel.NORMAL
    assert ladder.is_trading_allowed() is True


def test_drawdown_ladder_yellow_breach(ladder) -> None:
    """Test transition to YELLOW alert at 12% drawdown."""
    # IBKR YELLOW starts at 12% (88k)
    level = ladder.update(87900.0)
    assert level == DrawdownLevel.YELLOW
    assert ladder.is_trading_allowed() is True


def test_drawdown_ladder_red_breach(ladder) -> None:
    """Test transition to RED at 25% drawdown. Trading is now ALLOWED but at 10% size (SETO V12.0)."""
    # IBKR RED starts at 25% (75k)
    level = ladder.update(74000.0)
    assert level == DrawdownLevel.RED
    # Red/Orange levels no longer block trading—they tighten the filter (90% reduction).
    assert ladder.is_trading_allowed() is True
    assert ladder.get_size_modifier() == 0.10


def test_peak_equity_tracking(ladder) -> None:
    """Test that peak equity is updated only when current equity exceeds it."""
    ladder.update(110000.0)
    assert ladder.peak_equity == 110000.0

    ladder.update(105000.0)
    assert ladder.peak_equity == 110000.0
    assert ladder.level == DrawdownLevel.NORMAL  # (110k - 105k) / 110k = 4.5% (below 7%)
