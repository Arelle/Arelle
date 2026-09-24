"""
See COPYRIGHT.md for copyright information.

The xBRL-CSV period representations accepted by table constraints.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from types import MappingProxyType

import calendar
from decimal import Decimal

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


_PeriodBounds = tuple[XsInstant, XsInstant]
_DAYS_PER_WEEK = 7
_MONTHS_PER_YEAR = 12
_MONTHS_PER_HALF = 6
_MONTHS_PER_QUARTER = 3


def _period_order(start: XsInstant, end: XsInstant) -> int:
    if start.zoned != end.zoned:
        # Only one end has a time zone, so compare both on the timeline as given.
        end = replace(end, zoned=start.zoned)
    order = start.compare(end)
    assert order is not None
    return order


def _parse_year_period(value: str) -> _PeriodBounds | None:
    match = _PERIOD_YEAR_PATTERN.fullmatch(value)
    if match is None:
        return None
    return _month_span_bounds(match, 1, _MONTHS_PER_YEAR)


def _parse_half_period(value: str) -> _PeriodBounds | None:
    match = _PERIOD_HALF_PATTERN.fullmatch(value)
    if match is None:
        return None
    half = int(match.group("half"))
    first_month = (half - 1) * _MONTHS_PER_HALF + 1
    return _month_span_bounds(match, first_month, _MONTHS_PER_HALF)


def _parse_quarter_period(value: str) -> _PeriodBounds | None:
    match = _PERIOD_QTR_PATTERN.fullmatch(value)
    if match is None:
        return None
    quarter = int(match.group("quarter"))
    first_month = (quarter - 1) * _MONTHS_PER_QUARTER + 1
    return _month_span_bounds(match, first_month, _MONTHS_PER_QUARTER)


def _parse_month_period(value: str) -> _PeriodBounds | None:
    match = _PERIOD_MONTH_PATTERN.fullmatch(value)
    if match is None:
        return None
    month = int(match.group("month"))
    return _month_span_bounds(match, month, 1)


def _month_span_bounds(match: regex.Match[str], first_month: int, months: int) -> _PeriodBounds:
    """Bounds of a span of whole months, which ends when the month after it starts."""
    year = xs_dates.year_number(match.group("year"))
    last_month = first_month + months - 1
    start = _month_start_instant(year, first_month)
    if last_month == 12:
        end = _month_start_instant(year + 1, 1)
    else:
        end = _month_start_instant(year, last_month + 1)
    return _bounds_for_suffix(match.group("suffix"), start, end)


def _parse_week_period(value: str) -> _PeriodBounds | None:
    match = _PERIOD_WEEK_PATTERN.fullmatch(value)
    if match is None:
        return None
    year = xs_dates.year_number(match.group("year"))
    start_day = _iso_week_one_monday(year) + (int(match.group("week")) - 1) * _DAYS_PER_WEEK
    # December 28th is always in the last ISO week of its year.
    if start_day > xs_dates.days_since_epoch(year, 12, 28):
        return None
    start = _day_instant(start_day)
    end = _day_instant(start_day + _DAYS_PER_WEEK)
    return _bounds_for_suffix(match.group("suffix"), start, end)


def _iso_week_one_monday(year: int) -> int:
    """Day number of the Monday starting ISO week 1, the week containing January 4th."""
    january_fourth = xs_dates.days_since_epoch(year, 1, 4)
    return january_fourth - calendar.weekday(year, 1, 4)


def _parse_day_period(value: str) -> _PeriodBounds | None:
    match = _PERIOD_SINGLE_DAY_PATTERN.fullmatch(value)
    if match is None:
        return None
    start = xs_dates.parse_date(match.group("date"))
    if start is None:
        return None
    return _bounds_for_suffix(match.group("suffix"), start, _day_instant(start.day + 1))


def _parse_instant_period(value: str) -> _PeriodBounds | None:
    """An explicit instant, or an abbreviated period with a start or end suffix."""
    bounds = _parse_iso_instant(value)
    if bounds is not None:
        return bounds
    if not value.endswith(("@start", "@end")):
        return None
    for parse in _ABBREVIATED_PERIOD_PARSERS:
        bounds = parse(value)
        if bounds is not None:
            return bounds
    return None


def _parse_iso_instant(value: str) -> _PeriodBounds | None:
    match = _PERIOD_ISO_PATTERN.fullmatch(value)
    if match is None or match.group("end") is not None:
        return None
    start = xs_dates.parse_date_time(match.group("start"))
    if start is None:
        return None
    return start, start


def _parse_iso_range(value: str) -> _PeriodBounds | None:
    match = _PERIOD_ISO_PATTERN.fullmatch(value)
    if match is None or match.group("end") is None:
        return None
    start = xs_dates.parse_date_time(match.group("start"))
    end = xs_dates.parse_date_time(match.group("end"))
    if start is None or end is None or _period_order(start, end) != -1:
        return None
    return start, end


def _parse_inclusive_dates(value: str) -> _PeriodBounds | None:
    match = _PERIOD_INCLUSIVE_DATES_PATTERN.fullmatch(value)
    if match is None:
        return None
    start = xs_dates.parse_date(match.group("start"))
    end = xs_dates.parse_date(match.group("end"))
    if start is None or end is None or start.compare(end) == 1:
        return None
    return start, _day_instant(end.day + 1)


def _bounds_for_suffix(suffix: str | None, start: XsInstant, end: XsInstant) -> _PeriodBounds:
    if suffix == "start":
        return start, start
    if suffix == "end":
        return end, end
    return start, end


def _month_start_instant(year: int, month: int) -> XsInstant:
    return _day_instant(xs_dates.days_since_epoch(year, month, 1))


def _day_instant(day: int) -> XsInstant:
    return XsInstant(day=day, second=Decimal(0), zoned=False)


_PeriodParser = Callable[[str], _PeriodBounds | None]

_ABBREVIATED_PERIOD_PARSERS: tuple[_PeriodParser, ...] = (
    _parse_year_period,
    _parse_half_period,
    _parse_quarter_period,
    _parse_week_period,
    _parse_month_period,
    _parse_day_period,
)

PERIOD_TYPE_PARSERS: Mapping[str, _PeriodParser] = MappingProxyType(
    {
        "year": _parse_year_period,
        "half": _parse_half_period,
        "quarter": _parse_quarter_period,
        "week": _parse_week_period,
        "month": _parse_month_period,
        "day": _parse_day_period,
        "instant": _parse_instant_period,
    }
)

PERIOD_TYPES = frozenset(PERIOD_TYPE_PARSERS)

_ALL_PERIOD_PARSERS: tuple[_PeriodParser, ...] = (
    *PERIOD_TYPE_PARSERS.values(),
    _parse_iso_range,
    _parse_inclusive_dates,
)


def parse_period(value: str) -> _PeriodBounds | None:
    """Returns the start and end instants of a valid xBRL-CSV period, or None.

    An instant period has the same start and end. Abbreviated periods and inclusive
    date ranges end at the start of the following day, so 2024-01-01..2024-01-31
    ends at 2024-02-01T00:00:00.
    """
    for parse in _ALL_PERIOD_PARSERS:
        bounds = parse(value)
        if bounds is not None:
            return bounds
    return None
