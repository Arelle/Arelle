from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re


EXCEL_EPOCH = datetime(1899, 12, 30)


@dataclass(frozen=True)
class InstantValue:
    dt: datetime


@dataclass(frozen=True)
class DateRangeValue:
    start: datetime
    end: datetime
    isForever: bool = False


@dataclass(frozen=True)
class TimeSpanValue:
    delta: timedelta


def to_excel_serial(dt: datetime) -> float:
    diff = dt - EXCEL_EPOCH
    return diff.days + (diff.seconds + diff.microseconds / 1_000_000.0) / 86400.0


def format_excel_serial(dt: datetime) -> str:
    serial = to_excel_serial(dt)
    if abs(serial - round(serial)) < 1e-12:
        return str(int(round(serial)))
    return f"{serial:.10f}".rstrip("0").rstrip(".")


def format_instant(value: InstantValue) -> str:
    dt = value.dt
    if (
        dt.hour == 0
        and dt.minute == 0
        and dt.second == 0
        and dt.microsecond == 0
        and dt.tzinfo is None
    ):
        return dt.date().isoformat()
    return dt.isoformat()


def parse_date_string(value: str) -> datetime:
    # Date only: YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # DateTime: YYYY-MM-DDTHH:MM:SS
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", value)
    if m:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        second = int(m.group(6))
        if hour == 24 and minute == 0 and second == 0:
            return datetime(year, month, day) + timedelta(days=1)
        return datetime(year, month, day, hour, minute, second)

    raise ValueError(f"Error converting date: {value!r}")


def parse_time_span_string(value: str) -> TimeSpanValue:
    # Supported subset: PnD, PnW, PnYnMnD, PTnH
    if value.startswith("-"):
        raise ValueError(f"Could not convert {value!r} into a time-period.")

    m = re.fullmatch(r"P(\d+)D", value)
    if m:
        return TimeSpanValue(timedelta(days=int(m.group(1))))

    m = re.fullmatch(r"P(\d+)W", value)
    if m:
        return TimeSpanValue(timedelta(days=int(m.group(1)) * 7))

    m = re.fullmatch(r"P(\d+)Y(\d+)M(\d+)D", value)
    if m:
        days = int(m.group(1)) * 365 + int(m.group(2)) * 30 + int(m.group(3))
        return TimeSpanValue(timedelta(days=days))

    m = re.fullmatch(r"P(\d+)Y", value)
    if m:
        return TimeSpanValue(timedelta(days=int(m.group(1)) * 365))

    m = re.fullmatch(r"P(\d+)M", value)
    if m:
        return TimeSpanValue(timedelta(days=int(m.group(1)) * 30))

    m = re.fullmatch(r"P(\d+)Y(\d+)M", value)
    if m:
        days = int(m.group(1)) * 365 + int(m.group(2)) * 30
        return TimeSpanValue(timedelta(days=days))

    m = re.fullmatch(r"PT(\d+)H", value)
    if m:
        return TimeSpanValue(timedelta(hours=int(m.group(1))))

    raise ValueError(f"Could not convert {value!r} into a time-period.")


def format_range(value: DateRangeValue) -> str:
    if value.isForever:
        return "forever"
    return f"{format_instant(InstantValue(value.start))} to {format_instant(InstantValue(value.end))}"
