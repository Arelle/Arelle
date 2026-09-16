"""
See COPYRIGHT.md for copyright information.

XML Schema date, dateTime, gYear and gYearMonth values with any year.

Arelle models limit years to the datetime range. Table constraints can be validated
without populating a model, so these types are parsed here without that limit.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from decimal import Decimal

import regex

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
    seconds = hour * 3600 + minute * 60 + second - _tz_offset_seconds(tz)
    # Decimal divmod truncates towards zero, so floor the carry into neighbouring days.
    carry = math.floor(seconds / _SECONDS_PER_DAY)
    return XsInstant(day=day_number + carry, second=seconds - carry * _SECONDS_PER_DAY, zoned=tz is not None)


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
    hour = int(groups.get("hour") or 0)
    minute = int(groups.get("minute") or 0)
    second = Decimal(groups.get("second") or 0)
    if hour == 24 and (minute != 0 or second != 0):
        return None
    return _instant(year, month, day, hour, minute, second, groups["tz"])


def parse_date(value: str) -> XsInstant | None:
    return _parse(_DATE_PATTERN, value)


def parse_date_time(value: str) -> XsInstant | None:
    return _parse(_DATE_TIME_PATTERN, value)


def parse_g_year(value: str) -> XsInstant | None:
    return _parse(_G_YEAR_PATTERN, value)


def parse_g_year_month(value: str) -> XsInstant | None:
    return _parse(_G_YEAR_MONTH_PATTERN, value)
