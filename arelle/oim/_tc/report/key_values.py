"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Any, NamedTuple

from arelle.ModelValue import QName
from arelle.oim._tc import xs_dates
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.types import (
    CORE_PERIOD,
    NORMALIZED_STRING,
    STRING,
    resolve_effective_lexical_type,
)
from arelle.oim._tc.periods import parse_period
from arelle.oim._tc.xs_dates import XsInstant
from arelle.XmlUtil import collapseWhitespace, replaceWhitespace
from arelle.XmlValidate import decimalPattern, integerPattern


class KeyValue(NamedTuple):
    """A key field value that orders by the value space of its type.

    Ranks put nulls before every typed value and unparseable literals after them.
    Within the typed rank the value is canonical, so lexical variants are equal.
    """

    rank: int
    value: Any


_NULL_RANK = 0
_TYPED_RANK = 1
_INVALID_RANK = 2
NULL_KEY_VALUE = KeyValue(_NULL_RANK, None)
KeyValues = tuple[KeyValue, ...]

_Parser = Callable[[str], object | None]
_InstantKey = tuple[int, Decimal, bool]

_BOOLEANS: Mapping[str, bool] = MappingProxyType(
    {
        "true": True,
        "1": True,
        "false": False,
        "0": False,
    }
)


class KeyFieldType:
    """Converts the effective values of one key field into key values."""

    def __init__(
        self,
        constraint: TCValueConstraint,
        namespaces: Mapping[str, str],
    ) -> None:
        lexical_type = resolve_effective_lexical_type(constraint.type, namespaces)
        self._normalise_whitespace = _whitespace_normaliser(constraint, lexical_type)
        self._parse = _select_parser(constraint, lexical_type)

    def key_value(self, value: str | None) -> KeyValue:
        if value is None:
            return NULL_KEY_VALUE
        typed_value = self._parse(self._normalise_whitespace(value))
        if typed_value is None:
            return KeyValue(_INVALID_RANK, value)
        return KeyValue(_TYPED_RANK, typed_value)


class SortTracker:
    """Checks that the key values of consecutive rows of one table strictly increase.

    A table is either sorted or not, so only the first row that breaks the order is
    reported.
    """

    def __init__(self) -> None:
        self.first: KeyValues | None = None
        self.last: KeyValues | None = None
        self._reported = False

    def add(self, key: KeyValues) -> bool:
        """Records a row's key value and returns False for the first row out of order."""
        if any(key_value.rank == _INVALID_RANK for key_value in key):
            # An invalid literal has no place in the order of its type, and its cell
            # is already reported.
            return True
        if self.first is None:
            self.first = key
        in_order = self.last is None or key > self.last
        self.last = key
        if in_order or self._reported:
            return True
        self._reported = True
        return False


def _whitespace_normaliser(
    constraint: TCValueConstraint,
    lexical_type: QName | None,
) -> Callable[[str], str]:
    if constraint.type == CORE_PERIOD:
        return collapseWhitespace
    if lexical_type is None or lexical_type == STRING:
        return _preserve
    if lexical_type == NORMALIZED_STRING:
        return replaceWhitespace
    return collapseWhitespace


def _select_parser(
    constraint: TCValueConstraint,
    lexical_type: QName | None,
) -> _Parser:
    if constraint.type == CORE_PERIOD:
        return _parse_period_value
    if lexical_type is None:
        return _preserve
    if lexical_type.localName == "duration":
        if constraint.duration_type == "yearMonth":
            return xs_dates.parse_year_month_duration
        if constraint.duration_type == "dayTime":
            return xs_dates.parse_day_time_duration
    return _PARSERS.get(lexical_type.localName, _preserve)


def _preserve(value: str) -> str:
    return value


def _parse_boolean(value: str) -> bool | None:
    return _BOOLEANS.get(value)


def _parse_integer(value: str) -> Decimal | None:
    if integerPattern.match(value) is None:
        return None
    # Decimal has no digit limit, unlike int.
    return Decimal(value)


def _parse_decimal(value: str) -> Decimal | None:
    if decimalPattern.match(value) is None:
        return None
    return Decimal(value)


def _instant_key(instant: XsInstant) -> _InstantKey:
    return instant.day, instant.second, instant.zoned


def _parse_date(value: str) -> _InstantKey | None:
    instant = xs_dates.parse_date(value)
    return _instant_key(instant) if instant is not None else None


def _parse_date_time(value: str) -> _InstantKey | None:
    instant = xs_dates.parse_date_time(value)
    return _instant_key(instant) if instant is not None else None


def _parse_g_year(value: str) -> _InstantKey | None:
    instant = xs_dates.parse_g_year(value)
    return _instant_key(instant) if instant is not None else None


def _parse_g_year_month(value: str) -> _InstantKey | None:
    instant = xs_dates.parse_g_year_month(value)
    return _instant_key(instant) if instant is not None else None


def _parse_period_value(value: str) -> tuple[_InstantKey, _InstantKey] | None:
    bounds = parse_period(value)
    if bounds is None:
        return None
    start, end = bounds
    return _instant_key(start), _instant_key(end)


_PARSERS: Mapping[str, _Parser] = MappingProxyType(
    {
        "boolean": _parse_boolean,
        "decimal": _parse_decimal,
        "integer": _parse_integer,
        "nonPositiveInteger": _parse_integer,
        "negativeInteger": _parse_integer,
        "long": _parse_integer,
        "int": _parse_integer,
        "short": _parse_integer,
        "byte": _parse_integer,
        "nonNegativeInteger": _parse_integer,
        "unsignedLong": _parse_integer,
        "unsignedInt": _parse_integer,
        "unsignedShort": _parse_integer,
        "unsignedByte": _parse_integer,
        "positiveInteger": _parse_integer,
        "date": _parse_date,
        "dateTime": _parse_date_time,
        "gYear": _parse_g_year,
        "gYearMonth": _parse_g_year_month,
        "gMonthDay": xs_dates.parse_g_month_day,
        "gDay": xs_dates.parse_g_day,
        "gMonth": xs_dates.parse_g_month,
        "time": xs_dates.parse_time,
    }
)
