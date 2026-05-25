from datetime import datetime
from zoneinfo import ZoneInfo

from market_calendar import is_us_equity_holiday, is_us_equity_market_open


def test_memorial_day_2026_is_closed() -> None:
    day = datetime(2026, 5, 25, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_us_equity_holiday(day.date())
    assert not is_us_equity_market_open(day)


def test_normal_weekday_market_hours_are_open() -> None:
    day = datetime(2026, 5, 26, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    assert not is_us_equity_holiday(day.date())
    assert is_us_equity_market_open(day)


def test_after_hours_are_closed() -> None:
    day = datetime(2026, 5, 26, 18, 0, tzinfo=ZoneInfo("America/New_York"))
    assert not is_us_equity_market_open(day)
