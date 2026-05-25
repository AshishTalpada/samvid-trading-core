"""Shared market-hours calendar for US equities."""

from __future__ import annotations

from datetime import date, datetime
from datetime import time as dt_time
from zoneinfo import ZoneInfo

NYSE_FULL_DAY_HOLIDAYS = {
    "2024-01-01",
    "2024-01-15",
    "2024-02-19",
    "2024-03-29",
    "2024-05-27",
    "2024-06-19",
    "2024-07-04",
    "2024-09-02",
    "2024-11-28",
    "2024-12-25",
    "2025-01-01",
    "2025-01-20",
    "2025-02-17",
    "2025-04-18",
    "2025-05-26",
    "2025-06-19",
    "2025-07-04",
    "2025-09-01",
    "2025-11-27",
    "2025-12-25",
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-06-19",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
    "2027-01-01",
    "2027-01-18",
    "2027-02-15",
    "2027-03-26",
    "2027-05-31",
    "2027-06-18",
    "2027-07-05",
    "2027-09-06",
    "2027-11-25",
    "2027-12-24",
}


def is_us_equity_holiday(day: date) -> bool:
    return day.isoformat() in NYSE_FULL_DAY_HOLIDAYS


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
