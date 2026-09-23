"""
See COPYRIGHT.md for copyright information.

XML Schema date, dateTime, gYear and gYearMonth values with any year, the
recurring time, gMonthDay, gDay and gMonth values as positions in their cycle in UTC,
and yearMonth and dayTime durations.

Arelle models limit years to the datetime range. Table constraints can be validated
without populating a model, so these types are parsed here without that limit.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from decimal import Decimal, localcontext

import regex

from arelle.oim._tc.common import EXACT_CONTEXT
from arelle.oim.const import XSD_TZ, XSD_YEAR

_YEAR = rf"(?P<year>{XSD_YEAR})"
_MONTH = r"(?P<month>0[1-9]|1[0-2])"
_DAY = r"(?P<day>0[1-9]|[12][0-9]|3[01])"
_TIME = r"(?P<hour>[01][0-9]|2[0-4]):(?P<minute>[0-5][0-9]):(?P<second>(?:[0-5][0-9]|60)(?:\.[0-9]+)?)"
_TZ = rf"(?P<tz>{XSD_TZ})?"

_DATE_PATTERN = regex.compile(rf"{_YEAR}-{_MONTH}-{_DAY}{_TZ}$")
_DATE_TIME_PATTERN = regex.compile(rf"{_YEAR}-{_MONTH}-{_DAY}T{_TIME}{_TZ}$")
_G_YEAR_PATTERN = regex.compile(rf"{_YEAR}{_TZ}$")
_G_YEAR_MONTH_PATTERN = regex.compile(rf"{_YEAR}-{_MONTH}{_TZ}$")
_TIME_PATTERN = regex.compile(rf"{_TIME}{_TZ}$")
_G_MONTH_DAY_PATTERN = regex.compile(rf"--{_MONTH}-{_DAY}{_TZ}$")
_G_DAY_PATTERN = regex.compile(rf"---{_DAY}{_TZ}$")
_G_MONTH_PATTERN = regex.compile(rf"--{_MONTH}{_TZ}$")

_SIGN = r"(?P<sign>-)?"
_YEARS = r"(?:(?P<years>[0-9]+)Y)?"
_MONTHS = r"(?:(?P<months>[0-9]+)M)?"
_DAYS = r"(?:(?P<days>[0-9]+)D)?"
_HOURS = r"(?:(?P<hours>[0-9]+)H)?"
_MINUTES = r"(?:(?P<minutes>[0-9]+)M)?"
_SECONDS = r"(?:(?P<seconds>[0-9]+(?:\.[0-9]+)?)S)?"

_YEAR_MONTH_DURATION_PATTERN = regex.compile(rf"{_SIGN}P(?!$){_YEARS}{_MONTHS}$")
_DAY_TIME_DURATION_PATTERN = regex.compile(
    rf"{_SIGN}P(?!$){_DAYS}(?:T(?!$){_HOURS}{_MINUTES}{_SECONDS})?$"
)

_SECONDS_PER_DAY = 86400
_MAX_TZ_OFFSET_SECONDS = 14 * 3600


@dataclass(frozen=True, slots=True)
class XsInstant:
    """A point on the XML Schema timeline as days from 1970-01-01 plus seconds into
    the day, normalised to UTC when a time zone is present."""

    day: int
    second: Decimal
    zoned: bool

    def compare(self, other: XsInstant) -> int | None:
        """Returns -1, 0 or 1 ordering self against other, or None when the order is
        indeterminate because exactly one of the two carries a time zone."""
        difference = self._total_seconds() - other._total_seconds()
        if self.zoned == other.zoned:
            return _sign(difference)
        if difference < -_MAX_TZ_OFFSET_SECONDS:
            return -1
        if difference > _MAX_TZ_OFFSET_SECONDS:
            return 1
        return None

    def _total_seconds(self) -> Decimal:
        return self.day * _SECONDS_PER_DAY + self.second


def _sign(value: Decimal) -> int:
    if value < 0:
        return -1
    if value > 0:
        return 1
    return 0


def days_since_epoch(year: int, month: int, day: int) -> int:
    """Days from 1970-01-01 to the given Gregorian date, for any integer year.

    This is Howard Hinnant's days_from_civil algorithm.
    """
    if month <= 2:
        year -= 1
    era = year // 400
    year_of_era = year - era * 400
    day_of_year = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - 719468


def _tz_offset_seconds(tz: str | None) -> int:
    if tz is None or tz == "Z":
        return 0
    hours = int(tz[1:3])
    minutes = int(tz[4:6])
    offset = hours * 3600 + minutes * 60
    return -offset if tz.startswith("-") else offset


def _instant(year: int, month: int, day: int, hour: int, minute: int, second: Decimal, tz: str | None) -> XsInstant:
    day_number = days_since_epoch(year, month, day)
    carry, seconds = _seconds_into_day(hour, minute, second, tz)
    return XsInstant(day=day_number + carry, second=seconds, zoned=tz is not None)


def _seconds_into_day(hour: int, minute: int, second: Decimal, tz: str | None) -> tuple[int, Decimal]:
    """The UTC seconds into the day and the whole days carried into neighbouring days."""
    with localcontext(EXACT_CONTEXT):
        seconds = hour * 3600 + minute * 60 + second - _tz_offset_seconds(tz)
        # Time zone offsets are at most 14 hours, so the carry is at most one day.
        if seconds < 0:
            return -1, seconds + _SECONDS_PER_DAY
        if seconds >= _SECONDS_PER_DAY:
            return 1, seconds - _SECONDS_PER_DAY
        return 0, seconds


def year_number(lexical_year: str) -> int:
    """The year on the timeline for an XML Schema year."""
    year = int(lexical_year)
    if year < 0:
        # XSD 1.0 has no year zero, so -0001 is the year before 0001.
        year += 1
    return year


def _parse(pattern: regex.Pattern[str], value: str) -> XsInstant | None:
    match = pattern.match(value)
    if match is None:
        return None
    groups = match.groupdict()
    if int(groups["year"]) == 0:
        return None
    year = year_number(groups["year"])
    month = int(groups.get("month") or 1)
    day = int(groups.get("day") or 1)
    if day > calendar.monthrange(year, month)[1]:
        return None
    time = _parse_time_groups(groups)
    if time is None:
        return None
    return _instant(year, month, day, *time, groups["tz"])


def _parse_time_groups(groups: dict[str, str | None]) -> tuple[int, int, Decimal] | None:
    hour = int(groups.get("hour") or 0)
    minute = int(groups.get("minute") or 0)
    second = Decimal(groups.get("second") or 0)
    if hour == 24 and (minute != 0 or second != 0):
        return None
    return hour, minute, second


def parse_date(value: str) -> XsInstant | None:
    return _parse(_DATE_PATTERN, value)


def parse_date_time(value: str) -> XsInstant | None:
    return _parse(_DATE_TIME_PATTERN, value)


def parse_g_year(value: str) -> XsInstant | None:
    return _parse(_G_YEAR_PATTERN, value)


def parse_g_year_month(value: str) -> XsInstant | None:
    return _parse(_G_YEAR_MONTH_PATTERN, value)


def parse_time(value: str) -> Decimal | None:
    """Seconds into the day in UTC, so lexical variants of one time compare equal."""
    match = _TIME_PATTERN.match(value)
    if match is None:
        return None
    time = _parse_time_groups(match.groupdict())
    if time is None:
        return None
    return _seconds_into_day(*time, match.group("tz"))[1]


def parse_g_month_day(value: str) -> Decimal | None:
    return _parse_recurring(_G_MONTH_DAY_PATTERN, value)


def parse_g_day(value: str) -> Decimal | None:
    return _parse_recurring(_G_DAY_PATTERN, value)


def parse_g_month(value: str) -> Decimal | None:
    return _parse_recurring(_G_MONTH_PATTERN, value)


def _parse_recurring(pattern: regex.Pattern[str], value: str) -> Decimal | None:
    """Seconds from the start of a fixed year in UTC, so values of one type compare."""
    match = pattern.match(value)
    if match is None:
        return None
    # XML Schema compares recurring dates in an arbitrary leap year, so February 29th exists.
    year = 2000
    groups = match.groupdict()
    month = int(groups.get("month") or 1)
    day = int(groups.get("day") or 1)
    if day > calendar.monthrange(year, month)[1]:
        return None
    instant = _instant(year, month, day, 0, 0, Decimal(0), match.group("tz"))
    return (instant.day - days_since_epoch(year, 1, 1)) * _SECONDS_PER_DAY + instant.second


def parse_year_month_duration(value: str) -> Decimal | None:
    """The length in months of a duration with only year and month parts."""
    match = _YEAR_MONTH_DURATION_PATTERN.match(value)
    if match is None:
        return None
    # Decimal parts have no digit limit, and the exact context keeps every digit.
    with localcontext(EXACT_CONTEXT):
        months = Decimal(match.group("years") or 0) * 12 + Decimal(match.group("months") or 0)
        return -months if match.group("sign") else months


def parse_day_time_duration(value: str) -> Decimal | None:
    """The length in seconds of a duration with only day and time parts."""
    match = _DAY_TIME_DURATION_PATTERN.match(value)
    if match is None:
        return None
    # Decimal parts have no digit limit, and the exact context keeps every digit.
    with localcontext(EXACT_CONTEXT):
        seconds = (
            Decimal(match.group("days") or 0) * _SECONDS_PER_DAY
            + Decimal(match.group("hours") or 0) * 3600
            + Decimal(match.group("minutes") or 0) * 60
            + Decimal(match.group("seconds") or 0)
        )
        return -seconds if match.group("sign") else seconds
