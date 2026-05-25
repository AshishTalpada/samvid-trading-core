from datetime import datetime
from zoneinfo import ZoneInfo

from market_calendar import (
    is_us_equity_holiday,
    is_us_equity_market_open,
    us_equity_full_day_holidays,
)


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


def test_future_year_holidays_are_generated_without_static_table() -> None:
    holidays = us_equity_full_day_holidays(2032)

    assert datetime(2032, 1, 1).date() in holidays
    assert datetime(2032, 3, 26).date() in holidays  # Good Friday
    assert datetime(2032, 5, 31).date() in holidays  # Memorial Day
    assert datetime(2032, 11, 25).date() in holidays  # Thanksgiving


def test_new_year_observed_on_prior_december() -> None:
    assert is_us_equity_holiday(datetime(2027, 12, 31).date())


def test_manual_closed_date_override(monkeypatch) -> None:
    monkeypatch.setenv("SOVEREIGN_US_EQUITY_CLOSED_DATES", "2030-08-12")
    assert is_us_equity_holiday(datetime(2030, 8, 12).date())
