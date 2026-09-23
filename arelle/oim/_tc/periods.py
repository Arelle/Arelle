"""
See COPYRIGHT.md for copyright information.

The xBRL-CSV period representations accepted by table constraints.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from types import MappingProxyType

import regex

from arelle.oim._tc import xs_dates
from arelle.oim._tc.xs_dates import XsInstant
from arelle.oim.const import XSD_TZ, XSD_YEAR

# The xBRL-CSV period representations with XML Schema years, which the OIM patterns
# limit to four digits. OIM periods require canonical UTC (Z), so +00:00 is rejected.
_PERIOD_YEAR = rf"(?!-?0000){XSD_YEAR}"
_PERIOD_DATE = rf"{_PERIOD_YEAR}-[0-9]{{2}}-[0-9]{{2}}"
_PERIOD_TIME = r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
_PERIOD_TZ = rf"(?![+-]00:00){XSD_TZ}"
_PERIOD_DATETIME = rf"{_PERIOD_DATE}T{_PERIOD_TIME}(?:{_PERIOD_TZ})?"
_PERIOD_SUFFIX = r"@(?P<suffix>start|end)"

_PERIOD_TZ_PATTERN = regex.compile(rf"{_PERIOD_TZ}$")
_PERIOD_ISO_PATTERN = regex.compile(rf"(?P<start>{_PERIOD_DATETIME})(?:/(?P<end>{_PERIOD_DATETIME}))?$")
_PERIOD_INCLUSIVE_DATES_PATTERN = regex.compile(rf"(?P<start>{_PERIOD_DATE})\.\.(?P<end>{_PERIOD_DATE})$")
_PERIOD_SINGLE_DAY_PATTERN = regex.compile(rf"(?P<date>{_PERIOD_DATE})(?:{_PERIOD_SUFFIX})?$")
_PERIOD_MONTH_PATTERN = regex.compile(rf"(?P<year>{_PERIOD_YEAR})-(?P<month>0[1-9]|1[0-2])(?:{_PERIOD_SUFFIX})?$")
_PERIOD_YEAR_PATTERN = regex.compile(rf"(?P<year>{_PERIOD_YEAR})(?:{_PERIOD_SUFFIX})?$")
_PERIOD_QTR_PATTERN = regex.compile(rf"(?P<year>{_PERIOD_YEAR})Q(?P<quarter>[1-4])(?:{_PERIOD_SUFFIX})?$")
_PERIOD_HALF_PATTERN = regex.compile(rf"(?P<year>{_PERIOD_YEAR})H(?P<half>[12])(?:{_PERIOD_SUFFIX})?$")
_PERIOD_WEEK_PATTERN = regex.compile(
    rf"(?P<year>{_PERIOD_YEAR})W(?P<week>0[1-9]|[1-4][0-9]|5[0-3])(?:{_PERIOD_SUFFIX})?$"
)


def period_time_zone_matches(value: str, time_zone: bool) -> bool:
    match = _PERIOD_ISO_PATTERN.fullmatch(value)
    if match is None:
        return not time_zone
    has_start_tz = _PERIOD_TZ_PATTERN.search(match.group("start")) is not None
    if end_val := match.group("end"):
        has_end_tz = _PERIOD_TZ_PATTERN.search(end_val) is not None
        return has_start_tz == has_end_tz == time_zone
    return time_zone == has_start_tz


def _period_order(start: XsInstant, end: XsInstant) -> int:
    if start.zoned != end.zoned:
        # Only one end has a time zone, so compare both on the timeline as given.
        end = replace(end, zoned=start.zoned)
    order = start.compare(end)
    assert order is not None
    return order


def _is_valid_year_period(value: str) -> bool:
    return _PERIOD_YEAR_PATTERN.fullmatch(value) is not None


def _is_valid_half_period(value: str) -> bool:
    return _PERIOD_HALF_PATTERN.fullmatch(value) is not None


def _is_valid_quarter_period(value: str) -> bool:
    return _PERIOD_QTR_PATTERN.fullmatch(value) is not None


def _is_valid_month_period(value: str) -> bool:
    return _PERIOD_MONTH_PATTERN.fullmatch(value) is not None


def _is_valid_week_period(value: str) -> bool:
    match = _PERIOD_WEEK_PATTERN.fullmatch(value)
    if match is None:
        return False
    week = int(match.group("week"))
    year = xs_dates.year_number(match.group("year"))
    return 1 <= week <= _iso_weeks_in_year(year)


def _iso_weeks_in_year(year: int) -> int:
    year_minus_1 = year - 1
    jan1_week_day = (year_minus_1 + year_minus_1 // 4 - year_minus_1 // 100 + year_minus_1 // 400) % 7
    is_leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 53 if (jan1_week_day == 3 or (is_leap_year and jan1_week_day == 2)) else 52


def _is_valid_day_period(value: str) -> bool:
    match = _PERIOD_SINGLE_DAY_PATTERN.fullmatch(value)
    if match is None:
        return False
    return xs_dates.parse_date(match.group("date")) is not None


def _is_valid_instant_period(value: str) -> bool:
    match = _PERIOD_ISO_PATTERN.fullmatch(value)
    if match is not None and match.group("end") is None:
        return xs_dates.parse_date_time(match.group("start")) is not None
    if value.endswith(("@start", "@end")):
        return any(v(value) for v in _ABBREVIATED_PERIOD_VALIDATORS)
    return False


def _is_valid_duration_period(value: str) -> bool:
    match = _PERIOD_ISO_PATTERN.fullmatch(value)
    if match is None or match.group("end") is None:
        return False
    start = xs_dates.parse_date_time(match.group("start"))
    end = xs_dates.parse_date_time(match.group("end"))
    return start is not None and end is not None and _period_order(start, end) == -1


def _is_valid_range_period(value: str) -> bool:
    match = _PERIOD_INCLUSIVE_DATES_PATTERN.fullmatch(value)
    if match is None:
        return False
    start = xs_dates.parse_date(match.group("start"))
    end = xs_dates.parse_date(match.group("end"))
    return start is not None and end is not None and start.compare(end) != 1


_ABBREVIATED_PERIOD_VALIDATORS: tuple[Callable[[str], bool], ...] = tuple(
    [
        _is_valid_year_period,
        _is_valid_half_period,
        _is_valid_quarter_period,
        _is_valid_week_period,
        _is_valid_month_period,
        _is_valid_day_period,
    ]
)


PERIOD_TYPE_VALIDATORS = MappingProxyType(
    {
        "year": _is_valid_year_period,
        "half": _is_valid_half_period,
        "quarter": _is_valid_quarter_period,
        "week": _is_valid_week_period,
        "month": _is_valid_month_period,
        "day": _is_valid_day_period,
        "instant": _is_valid_instant_period,
    }
)

_ALL_PERIOD_VALIDATORS = tuple(
    [
        *PERIOD_TYPE_VALIDATORS.values(),
        _is_valid_duration_period,
        _is_valid_range_period,
    ]
)


def is_valid_period(value: str) -> bool:
    return any(validator(value) for validator in _ALL_PERIOD_VALIDATORS)
