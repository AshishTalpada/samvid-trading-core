"""Shared regular-session calendar for US equities.

This intentionally covers deterministic NYSE/Nasdaq full-day closures without a
network dependency. Unscheduled closures still need an operational override.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from zoneinfo import ZoneInfo

_FULL_DAY_OVERRIDE_ENV = "SOVEREIGN_US_EQUITY_CLOSED_DATES"
_OPEN_OVERRIDE_ENV = "SOVEREIGN_US_EQUITY_OPEN_DATES"


def _parse_override_dates(env_name: str) -> set[date]:
    raw = os.environ.get(env_name, "")
    dates: set[date] = set()
    for item in raw.replace(";", ",").split(","):
        value = item.strip()
        if not value:
            continue
        try:
            dates.add(date.fromisoformat(value))
        except ValueError:
            continue
    return dates


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    day = date(year, month, 1)
    offset = (weekday - day.weekday()) % 7
    return day + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        day = date(year, month + 1, 1) - timedelta(days=1)
    return day - timedelta(days=(day.weekday() - weekday) % 7)


def _observed_fixed(month: int, day: int, year: int) -> date:
    actual = date(year, month, day)
    if actual.weekday() == 5:
        return actual - timedelta(days=1)
    if actual.weekday() == 6:
        return actual + timedelta(days=1)
    return actual


def _good_friday(year: int) -> date:
    # Anonymous Gregorian computus for Easter Sunday, then subtract two days.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    easter_month = (h + l - 7 * m + 114) // 31
    easter_day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, easter_month, easter_day) - timedelta(days=2)


def us_equity_full_day_holidays(year: int) -> set[date]:
    """Return deterministic full-day NYSE/Nasdaq holidays for a calendar year."""
    holidays = {
        _observed_fixed(1, 1, year),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday / Presidents Day
        _good_friday(year),
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed_fixed(7, 4, year),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed_fixed(12, 25, year),
    }
    if year >= 2022:
        holidays.add(_observed_fixed(6, 19, year))  # Juneteenth

    next_new_year_observed = _observed_fixed(1, 1, year + 1)
    if next_new_year_observed.year == year:
        holidays.add(next_new_year_observed)

    return {holiday for holiday in holidays if holiday.year == year}


def is_us_equity_holiday(day: date) -> bool:
    if day in _parse_override_dates(_OPEN_OVERRIDE_ENV):
        return False
    if day in _parse_override_dates(_FULL_DAY_OVERRIDE_ENV):
        return True
    return day in us_equity_full_day_holidays(day.year)


def is_us_equity_market_open(now: datetime | None = None) -> bool:
    """Return True during regular NYSE/Nasdaq 9:30-16:00 ET sessions."""
    try:
        et_tz = ZoneInfo("America/New_York")
        now_et = now.astimezone(et_tz) if now else datetime.now(et_tz)
        if now_et.weekday() >= 5:
            return False
        if is_us_equity_holiday(now_et.date()):
            return False
        return dt_time(9, 30) <= now_et.time() < dt_time(16, 0)
    except Exception:
        return False
