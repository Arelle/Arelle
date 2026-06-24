"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, cast

import regex

from arelle.ModelValue import DateTime, QName, TypeXValue
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.types import (
    CORE_ENTITY,
    CORE_LANGUAGE,
    CORE_PERIOD,
    CORE_UNIT,
    DATE,
    DATE_TIME,
    QNAME,
    resolve_effective_lexical_type,
)
from arelle.oim.const import (
    PER_HALF_PATTERN,
    PER_INCLUSIVE_DATES_PATTERN,
    PER_ISO_PATTERN,
    PER_MONTH_PATTERN,
    PER_QTR_PATTERN,
    PER_SINGLE_DAY_PATTERN,
    PER_TZ_PATTERN,
    PER_WEEK_PATTERN,
    PER_YEAR_PATTERN,
    PREFIXED_QNAME_PATTERN,
    SQNAME_PATTERN,
    UNIT_PATTERN,
    UNIT_QNAME_SUBSTITUTION_CHAR,
)
from arelle.XmlValidate import XmlValidationResult, XsdPattern, validateFacetValueString, validateValueString

# TC prohibits uppercase characters in core language.
_TC_CORE_LANGUAGE_PATTERN = regex.compile(r"[a-z]{1,8}(-[a-z0-9]{1,8})*$")


class ValueConstraintValidator:
    def __init__(self, constraint: TCValueConstraint, namespaces: Mapping[str, str]) -> None:
        self._constraint = constraint
        self._namespaces = namespaces
        self._effective_lexical_type = resolve_effective_lexical_type(constraint.type, namespaces)
        self._facets = self._build_facets()
        self._compiled_patterns = self._compile_patterns()

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

    def _compile_patterns(self) -> tuple[XsdPattern, ...]:
        if not self._constraint.patterns:
            return ()
        compiled = []
        for pattern in self._constraint.patterns:
            with contextlib.suppress(ValueError, regex.error):
                compiled.append(XsdPattern.compile(pattern))
        return tuple(compiled)

    def validate(self, value: str) -> bool:
        if self._effective_lexical_type is None:
            return False
        typed_value_result = self._validate_base_type(self._effective_lexical_type, value)
        if not typed_value_result.isXValid:
            return False
        if not self._is_patterns_valid(value):
            return False
        if self._effective_lexical_type == QNAME:
            tc_valid_qname = self._is_valid_qname(typed_value_result.xValue)
            if not tc_valid_qname:
                return False
        if self._constraint.type == CORE_ENTITY:
            tc_valid_sqname = self._is_valid_sqname(value)
            if not tc_valid_sqname:
                return False
        if self._constraint.type == CORE_LANGUAGE:
            tc_valid_language = self._is_valid_core_language(value)
            if not tc_valid_language:
                return False
        if self._constraint.type == CORE_UNIT:
            tc_valid_unit = self._is_valid_unit(value)
            if not tc_valid_unit:
                return False
        if self._constraint.type == CORE_PERIOD:
            if self._constraint.period_type is not None:
                validator = PERIOD_TYPE_VALIDATORS.get(self._constraint.period_type)
                if validator is None or not validator(value):
                    return False
            elif not any(validator(value) for validator in _ALL_PERIOD_VALIDATORS):
                return False
        return True

    def _validate_base_type(self, base_xsd_type: QName, value_string: str) -> XmlValidationResult:
        return validateValueString(
            base_xsd_type.localName,
            value_string,
            facets=self._facets,
            nsmap=cast(Mapping[str | None, str], self._namespaces),
        )

    def _is_patterns_valid(self, value: str) -> bool:
        if not self._compiled_patterns:
            return True
        return any(pattern.match(value) is not None for pattern in self._compiled_patterns)

    def _is_valid_qname(self, typed_value: TypeXValue) -> bool:
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


def _parse_date(value: str) -> DateTime | None:
    return _parse_date_or_datetime(value, DATE)


def _parse_datetime(value: str) -> DateTime | None:
    return _parse_date_or_datetime(value, DATE_TIME)


def _parse_date_or_datetime(value: str, xsd_type: QName) -> DateTime | None:
    stripped = PER_TZ_PATTERN.sub("", value)
    result = validateValueString(xsd_type.localName, stripped)
    if result.isXValid and isinstance(result.xValue, DateTime):
        return result.xValue
    return None


def _is_valid_year_period(value: str) -> bool:
    return PER_YEAR_PATTERN.fullmatch(value) is not None


def _is_valid_half_period(value: str) -> bool:
    return PER_HALF_PATTERN.fullmatch(value) is not None


def _is_valid_quarter_period(value: str) -> bool:
    return PER_QTR_PATTERN.fullmatch(value) is not None


def _is_valid_month_period(value: str) -> bool:
    return PER_MONTH_PATTERN.fullmatch(value) is not None


def _is_valid_week_period(value: str) -> bool:
    match = PER_WEEK_PATTERN.fullmatch(value)
    if match is None:
        return False
    week = int(match.group("week"))
    year = int(match.group("year"))
    return 1 <= week <= _iso_weeks_in_year(year)


def _iso_weeks_in_year(year: int) -> int:
    year_minus_1 = year - 1
    jan1_week_day = (year_minus_1 + year_minus_1 // 4 - year_minus_1 // 100 + year_minus_1 // 400) % 7
    is_leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return 53 if (jan1_week_day == 3 or (is_leap_year and jan1_week_day == 2)) else 52


def _is_valid_day_period(value: str) -> bool:
    match = PER_SINGLE_DAY_PATTERN.fullmatch(value)
    if match is None:
        return False
    date_group = match.group("date")
    return _parse_date(date_group) is not None


def _is_valid_instant_period(value: str) -> bool:
    match = PER_ISO_PATTERN.fullmatch(value)
    if match is not None and match.group("end") is None:
        return _parse_datetime(match.group("start")) is not None
    if value.endswith(("@start", "@end")):
        return any(v(value) for v in _ABBREVIATED_PERIOD_VALIDATORS)
    return False


def _is_valid_duration_period(value: str) -> bool:
    match = PER_ISO_PATTERN.fullmatch(value)
    if match is None:
        return False
    start_group = match.group("start")
    end_group = match.group("end")
    if start_group is None or end_group is None:
        return False
    start_dt = _parse_datetime(start_group)
    end_dt = _parse_datetime(end_group)
    return start_dt is not None and end_dt is not None and start_dt < end_dt


def _is_valid_range_period(value: str) -> bool:
    match = PER_INCLUSIVE_DATES_PATTERN.fullmatch(value)
    if match is None:
        return False
    start_dt = _parse_date(match.group("start"))
    end_dt = _parse_date(match.group("end"))
    return start_dt is not None and end_dt is not None and start_dt <= end_dt


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
