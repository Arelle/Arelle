"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Callable, Mapping
from types import MappingProxyType
from dataclasses import dataclass, replace
from typing import Any, cast

import regex

from arelle.ModelValue import QName, TypeXValue, dayTimeDuration, yearMonthDuration
from arelle.oim._tc import xs_dates
from arelle.oim._tc.xs_dates import XsInstant
from arelle.oim._tc.const import (
    TCRE_INVALID_DURATION_TYPE,
    TCRE_INVALID_PERIOD_TYPE,
    TCRE_INVALID_VALUE,
    TCRE_MISSING_TIME_ZONE,
    TCRE_UNEXPECTED_TIME_ZONE,
)
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.types import (
    CORE_ENTITY,
    CORE_LANGUAGE,
    CORE_PERIOD,
    CORE_UNIT,
    NORMALIZED_STRING,
    OPTIONALLY_TIME_ZONED_TYPES,
    QNAME,
    STRING,
    resolve_effective_lexical_type,
)
from arelle.oim.const import (
    PREFIXED_QNAME_PATTERN,
    SQNAME_PATTERN,
    UNIT_PATTERN,
    UNIT_QNAME_SUBSTITUTION_CHAR,
    XSD_TZ,
    XSD_TZ_PATTERN,
    XSD_YEAR,
)
from arelle.XmlUtil import collapseWhitespace, replaceWhitespace
from arelle.XmlValidate import XmlValidationResult, XsdPattern, validateFacetValueString, validateValueString

# TC prohibits uppercase characters in core language.
_TC_CORE_LANGUAGE_PATTERN = regex.compile(r"[a-z]{1,8}(-[a-z0-9]{1,8})*$")

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



@dataclass(frozen=True, slots=True)
class _TypedValue:
    is_valid: bool
    value: TypeXValue | XsInstant = None


_INVALID_TYPED_VALUE = _TypedValue(is_valid=False)

_BOUNDS_FACET_ALLOWED_ORDERS: Mapping[str, frozenset[int]] = MappingProxyType(
    {
        "minInclusive": frozenset({0, 1}),
        "maxInclusive": frozenset({-1, 0}),
        "minExclusive": frozenset({1}),
        "maxExclusive": frozenset({-1}),
    }
)


# Types validated without the model, so their years are not limited to the datetime range.
_WIDE_YEAR_PARSERS: Mapping[str, Callable[[str], XsInstant | None]] = MappingProxyType(
    {
        "date": xs_dates.parse_date,
        "dateTime": xs_dates.parse_date_time,
        "gYear": xs_dates.parse_g_year,
        "gYearMonth": xs_dates.parse_g_year_month,
    }
)


class ValueConstraintValidator:
    def __init__(self, constraint: TCValueConstraint, namespaces: Mapping[str, str]) -> None:
        self._constraint = constraint
        self._namespaces = namespaces
        self._effective_lexical_type = resolve_effective_lexical_type(constraint.type, namespaces)
        self._wide_year_parser = None
        if self._effective_lexical_type is not None:
            self._wide_year_parser = _WIDE_YEAR_PARSERS.get(self._effective_lexical_type.localName)
        self._facets: Mapping[str, Any] = MappingProxyType({})
        self._wide_year_bounds: tuple[tuple[str, XsInstant], ...] = ()
        if self._wide_year_parser is None:
            self._facets = self._build_facets()
        else:
            self._wide_year_bounds = self._build_wide_year_bounds()
        self._compiled_patterns = self._compile_patterns()
        self._enumeration_typed_values = self._typed_enumeration_values()

    def _build_facets(self) -> Mapping[str, Any]:
        if self._effective_lexical_type is None:
            return MappingProxyType({})
        facets: dict[str, Any] = {}
        if self._constraint.length is not None:
            facets["length"] = self._constraint.length
        if self._constraint.min_length is not None:
            facets["minLength"] = self._constraint.min_length
        if self._constraint.max_length is not None:
            facets["maxLength"] = self._constraint.max_length
        if self._constraint.total_digits is not None:
            facets["totalDigits"] = self._constraint.total_digits
        if self._constraint.fraction_digits is not None:
            facets["fractionDigits"] = self._constraint.fraction_digits
        for facet_name, raw_value in (
            ("minInclusive", self._constraint.min_inclusive),
            ("maxInclusive", self._constraint.max_inclusive),
            ("minExclusive", self._constraint.min_exclusive),
            ("maxExclusive", self._constraint.max_exclusive),
        ):
            if raw_value is not None:
                result = validateFacetValueString(facet_name, raw_value, self._effective_lexical_type.localName)
                if result.isXValid and not isinstance(result.xValue, str):
                    facets[facet_name] = result.xValue
        return MappingProxyType(facets)

    def _build_wide_year_bounds(self) -> tuple[tuple[str, XsInstant], ...]:
        """Bounds facets as instants. Unparseable bounds are reported by metadata validation."""
        bounds = []
        for facet_name, raw_value in (
            ("minInclusive", self._constraint.min_inclusive),
            ("maxInclusive", self._constraint.max_inclusive),
            ("minExclusive", self._constraint.min_exclusive),
            ("maxExclusive", self._constraint.max_exclusive),
        ):
            if raw_value is None:
                continue
            bound = self._parse_wide_year(raw_value)
            if bound is not None:
                bounds.append((facet_name, bound))
        return tuple(bounds)

    def _parse_wide_year(self, value: str) -> XsInstant | None:
        assert self._wide_year_parser is not None
        return self._wide_year_parser(collapseWhitespace(value))

    def _typed_enumeration_values(self) -> frozenset[object] | None:
        """Enumeration members in the value space, so lexically different forms of one value match."""
        if self._constraint.enumeration_values is None or self._effective_lexical_type is None:
            return None
        typed_values = set()
        for member in self._constraint.enumeration_values:
            result = self._typed_value(member)
            if result.is_valid:
                typed_values.add(result.value)
        return frozenset(typed_values)

    def _compile_patterns(self) -> tuple[XsdPattern, ...]:
        if not self._constraint.patterns:
            return ()
        compiled = []
        for pattern in self._constraint.patterns:
            with contextlib.suppress(ValueError, regex.error):
                compiled.append(XsdPattern.compile(pattern))
        return tuple(compiled)

    def validate(self, value: str) -> bool:
        return self.first_violation(value) is None

    def first_violation(self, value: str) -> str | None:
        """Returns the tcre error code for the first constraint the value violates, or None if it satisfies all."""
        if self._effective_lexical_type is None:
            return TCRE_INVALID_VALUE
        typed_value = self._typed_value(value, with_facets=True)
        if not typed_value.is_valid:
            return TCRE_INVALID_VALUE
        value = self._normalized_lexical_value(value)
        if not self._is_patterns_valid(value):
            return TCRE_INVALID_VALUE
        if not self._is_enumeration_valid(typed_value.value):
            return TCRE_INVALID_VALUE
        if self._effective_lexical_type == QNAME and not self._is_valid_qname(typed_value.value):
            return TCRE_INVALID_VALUE
        if self._constraint.type == CORE_ENTITY and not self._is_valid_sqname(value):
            return TCRE_INVALID_VALUE
        if self._constraint.type == CORE_LANGUAGE and not self._is_valid_core_language(value):
            return TCRE_INVALID_VALUE
        if self._constraint.type == CORE_UNIT and not self._is_valid_unit(value):
            return TCRE_INVALID_VALUE
        if self._constraint.type == CORE_PERIOD:
            if not any(validator(value) for validator in _ALL_PERIOD_VALIDATORS):
                return TCRE_INVALID_VALUE
            if self._constraint.period_type is not None:
                validator = PERIOD_TYPE_VALIDATORS.get(self._constraint.period_type)
                if validator is None or not validator(value):
                    return TCRE_INVALID_PERIOD_TYPE
        if not self._is_duration_type_valid(value):
            return TCRE_INVALID_DURATION_TYPE
        if not self._is_time_zone_valid(value):
            return TCRE_MISSING_TIME_ZONE if self._constraint.time_zone else TCRE_UNEXPECTED_TIME_ZONE
        return None

    def _typed_value(self, value: str, with_facets: bool = False) -> _TypedValue:
        """Parses value in the effective type, applying the bounds and length facets when asked."""
        assert self._effective_lexical_type is not None
        if self._wide_year_parser is None:
            result = self._validate_base_type(self._effective_lexical_type, value, self._facets if with_facets else None)
            return _TypedValue(result.isXValid, result.xValue)
        instant = self._parse_wide_year(value)
        if instant is None:
            return _INVALID_TYPED_VALUE
        if with_facets:
            for facet_name, bound in self._wide_year_bounds:
                if instant.compare(bound) not in _BOUNDS_FACET_ALLOWED_ORDERS[facet_name]:
                    return _INVALID_TYPED_VALUE
        return _TypedValue(True, instant)

    def _validate_base_type(
        self,
        base_xsd_type: QName,
        value_string: str,
        facets: Mapping[str, Any] | None = None,
    ) -> XmlValidationResult:
        return validateValueString(
            base_xsd_type.localName,
            value_string,
            facets=facets,
            nsmap=cast(Mapping[str | None, str], self._namespaces),
        )

    def _normalized_lexical_value(self, value: str) -> str:
        if self._effective_lexical_type == STRING:
            return value
        if self._effective_lexical_type == NORMALIZED_STRING:
            return replaceWhitespace(value)
        return collapseWhitespace(value)

    def _is_enumeration_valid(self, typed_value: TypeXValue | XsInstant) -> bool:
        if self._enumeration_typed_values is None:
            return True
        if typed_value in self._enumeration_typed_values:
            return True
        # XML Schema treats NaN as equal to itself, Python floats do not.
        return (
            isinstance(typed_value, float)
            and math.isnan(typed_value)
            and any(isinstance(member, float) and math.isnan(member) for member in self._enumeration_typed_values)
        )

    def _is_patterns_valid(self, value: str) -> bool:
        if not self._compiled_patterns:
            return True
        return any(pattern.match(value) is not None for pattern in self._compiled_patterns)

    def _is_valid_qname(self, typed_value: TypeXValue | XsInstant) -> bool:
        if not isinstance(typed_value, QName):
            return False
        if not typed_value.prefix:
            # Local only QNames are prohibited.
            return False
        return typed_value.prefix in self._namespaces

    def _is_valid_sqname(self, value: str) -> bool:
        sqname_match = SQNAME_PATTERN.fullmatch(value)
        if sqname_match is None:
            return False
        prefix = sqname_match.group("prefix")
        return prefix is not None and prefix in self._namespaces

    def _is_valid_core_language(self, value: str) -> bool:
        return _TC_CORE_LANGUAGE_PATTERN.fullmatch(value) is not None

    def _is_duration_type_valid(self, value: str) -> bool:
        if self._constraint.duration_type is None:
            return True
        try:
            match self._constraint.duration_type:
                case "yearMonth":
                    yearMonthDuration(value)
                case "dayTime":
                    dayTimeDuration(value)
        except ValueError:
            return False
        return True

    def _is_time_zone_valid(self, value: str) -> bool:
        if self._constraint.time_zone is None:
            return True
        if self._constraint.type == CORE_PERIOD:
            return self._period_timezone_matches(value)
        if self._effective_lexical_type in OPTIONALLY_TIME_ZONED_TYPES:
            has_tz = XSD_TZ_PATTERN.search(value) is not None
            return self._constraint.time_zone == has_tz
        return True

    def _period_timezone_matches(self, value: str) -> bool:
        match = _PERIOD_ISO_PATTERN.fullmatch(value)
        if match is None:
            return not self._constraint.time_zone
        has_start_tz = _PERIOD_TZ_PATTERN.search(match.group("start")) is not None
        if end_val := match.group("end"):
            has_end_tz = _PERIOD_TZ_PATTERN.search(end_val) is not None
            return has_start_tz == has_end_tz == self._constraint.time_zone
        return self._constraint.time_zone == has_start_tz

    def _is_valid_unit(self, value: str) -> bool:
        unit_qnames = PREFIXED_QNAME_PATTERN.findall(value)
        if not unit_qnames:
            return False
        substituted = PREFIXED_QNAME_PATTERN.sub(UNIT_QNAME_SUBSTITUTION_CHAR, value)
        if UNIT_PATTERN.fullmatch(substituted) is None:
            return False
        for unit_qname in unit_qnames:
            qname_validation_result = self._validate_base_type(QNAME, unit_qname)
            if not qname_validation_result.isXValid:
                return False
            if not self._is_valid_qname(qname_validation_result.xValue):
                return False
        numerator, _, denominator = value.partition("/")
        return self._is_sorted_product(numerator) and self._is_sorted_product(denominator)

    def _is_sorted_product(self, product: str) -> bool:
        if not product:
            return True
        if product.startswith("(") and product.endswith(")"):
            product = product[1:-1]
        qnames = product.split("*")
        return qnames == sorted(qnames)


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
