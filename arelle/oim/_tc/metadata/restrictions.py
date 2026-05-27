"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from enum import Enum
from types import MappingProxyType

from arelle.ModelValue import QName
from arelle.oim._tc.metadata import types as tc_types
from arelle.oim._tc.metadata.model import TCValueConstraint


class TCRestriction(str, Enum):
    ENUMERATION_VALUES = "enumerationValues"
    PATTERNS = "patterns"
    TIME_ZONE = "timeZone"
    PERIOD_TYPE = "periodType"
    DURATION_TYPE = "durationType"
    LENGTH = "length"
    MIN_LENGTH = "minLength"
    MAX_LENGTH = "maxLength"
    MIN_INCLUSIVE = "minInclusive"
    MAX_INCLUSIVE = "maxInclusive"
    MIN_EXCLUSIVE = "minExclusive"
    MAX_EXCLUSIVE = "maxExclusive"
    TOTAL_DIGITS = "totalDigits"
    FRACTION_DIGITS = "fractionDigits"


PATTERN_AND_ENUM_RESTRICTIONS = frozenset(
    {
        TCRestriction.PATTERNS,
        TCRestriction.ENUMERATION_VALUES,
    }
)
LENGTH_RESTRICTIONS = frozenset(
    {
        TCRestriction.LENGTH,
        TCRestriction.MIN_LENGTH,
        TCRestriction.MAX_LENGTH,
    }
)
BOUNDS_RESTRICTIONS = frozenset(
    {
        TCRestriction.MIN_INCLUSIVE,
        TCRestriction.MAX_INCLUSIVE,
        TCRestriction.MIN_EXCLUSIVE,
        TCRestriction.MAX_EXCLUSIVE,
    }
)
DIGIT_RESTRICTIONS = frozenset(
    {
        TCRestriction.TOTAL_DIGITS,
        TCRestriction.FRACTION_DIGITS,
    }
)

BOOLEAN_RESTRICTIONS = frozenset({TCRestriction.PATTERNS})
ORDERED_RESTRICTIONS = BOUNDS_RESTRICTIONS | PATTERN_AND_ENUM_RESTRICTIONS
STRING_RESTRICTIONS = LENGTH_RESTRICTIONS | PATTERN_AND_ENUM_RESTRICTIONS
DURATION_RESTRICTIONS = ORDERED_RESTRICTIONS | frozenset({TCRestriction.DURATION_TYPE})
PERIOD_RESTRICTIONS = STRING_RESTRICTIONS | frozenset({TCRestriction.TIME_ZONE, TCRestriction.PERIOD_TYPE})
TIME_ZONED_RESTRICTIONS = ORDERED_RESTRICTIONS | frozenset({TCRestriction.TIME_ZONE})
NUMERIC_RESTRICTIONS = ORDERED_RESTRICTIONS | DIGIT_RESTRICTIONS

CORE_TYPE_RESTRICTIONS: Mapping[str, frozenset[TCRestriction]] = MappingProxyType(
    {
        tc_types.CORE_CONCEPT: PATTERN_AND_ENUM_RESTRICTIONS,
        tc_types.CORE_ENTITY: STRING_RESTRICTIONS,
        tc_types.CORE_PERIOD: PERIOD_RESTRICTIONS,
        tc_types.CORE_UNIT: STRING_RESTRICTIONS,
        tc_types.CORE_LANGUAGE: STRING_RESTRICTIONS,
        tc_types.CORE_DECIMALS: NUMERIC_RESTRICTIONS,
    }
)

_SCHEMA_TYPE_RESTRICTIONS: Mapping[QName, frozenset[TCRestriction]] = MappingProxyType(
    {
        tc_types.ANY_URI: STRING_RESTRICTIONS,
        tc_types.BASE64_BINARY: STRING_RESTRICTIONS,
        tc_types.BOOLEAN: BOOLEAN_RESTRICTIONS,
        tc_types.BYTE: NUMERIC_RESTRICTIONS,
        tc_types.DATE: TIME_ZONED_RESTRICTIONS,
        tc_types.DATE_TIME: TIME_ZONED_RESTRICTIONS,
        tc_types.DECIMAL: NUMERIC_RESTRICTIONS,
        tc_types.DOUBLE: ORDERED_RESTRICTIONS,
        tc_types.DURATION: DURATION_RESTRICTIONS,
        tc_types.FLOAT: ORDERED_RESTRICTIONS,
        tc_types.G_DAY: TIME_ZONED_RESTRICTIONS,
        tc_types.G_MONTH: TIME_ZONED_RESTRICTIONS,
        tc_types.G_MONTH_DAY: TIME_ZONED_RESTRICTIONS,
        tc_types.G_YEAR: TIME_ZONED_RESTRICTIONS,
        tc_types.G_YEAR_MONTH: TIME_ZONED_RESTRICTIONS,
        tc_types.HEX_BINARY: STRING_RESTRICTIONS,
        tc_types.INT: NUMERIC_RESTRICTIONS,
        tc_types.INTEGER: NUMERIC_RESTRICTIONS,
        tc_types.LANGUAGE: STRING_RESTRICTIONS,
        tc_types.LONG: NUMERIC_RESTRICTIONS,
        tc_types.NAME: STRING_RESTRICTIONS,
        tc_types.NC_NAME: STRING_RESTRICTIONS,
        tc_types.NEGATIVE_INTEGER: NUMERIC_RESTRICTIONS,
        tc_types.NON_NEGATIVE_INTEGER: NUMERIC_RESTRICTIONS,
        tc_types.NON_POSITIVE_INTEGER: NUMERIC_RESTRICTIONS,
        tc_types.NORMALIZED_STRING: STRING_RESTRICTIONS,
        tc_types.POSITIVE_INTEGER: NUMERIC_RESTRICTIONS,
        tc_types.QNAME: PATTERN_AND_ENUM_RESTRICTIONS,
        tc_types.SHORT: NUMERIC_RESTRICTIONS,
        tc_types.STRING: STRING_RESTRICTIONS,
        tc_types.TIME: TIME_ZONED_RESTRICTIONS,
        tc_types.TOKEN: STRING_RESTRICTIONS,
        tc_types.UNSIGNED_BYTE: NUMERIC_RESTRICTIONS,
        tc_types.UNSIGNED_INT: NUMERIC_RESTRICTIONS,
        tc_types.UNSIGNED_LONG: NUMERIC_RESTRICTIONS,
        tc_types.UNSIGNED_SHORT: NUMERIC_RESTRICTIONS,
    }
)


def get_constraint_values_by_restriction(
    constraint: TCValueConstraint,
) -> Mapping[TCRestriction, Set[str] | str | int | bool | None]:
    return MappingProxyType(
        {
            TCRestriction.ENUMERATION_VALUES: constraint.enumeration_values,
            TCRestriction.PATTERNS: constraint.patterns,
            TCRestriction.TIME_ZONE: constraint.time_zone,
            TCRestriction.PERIOD_TYPE: constraint.period_type,
            TCRestriction.DURATION_TYPE: constraint.duration_type,
            TCRestriction.LENGTH: constraint.length,
            TCRestriction.MIN_LENGTH: constraint.min_length,
            TCRestriction.MAX_LENGTH: constraint.max_length,
            TCRestriction.MIN_INCLUSIVE: constraint.min_inclusive,
            TCRestriction.MAX_INCLUSIVE: constraint.max_inclusive,
            TCRestriction.MIN_EXCLUSIVE: constraint.min_exclusive,
            TCRestriction.MAX_EXCLUSIVE: constraint.max_exclusive,
            TCRestriction.TOTAL_DIGITS: constraint.total_digits,
            TCRestriction.FRACTION_DIGITS: constraint.fraction_digits,
        }
    )


def permitted_restrictions(constraint_type: str, effective_type: QName) -> frozenset[TCRestriction]:
    if core_restrictions := CORE_TYPE_RESTRICTIONS.get(constraint_type):
        return core_restrictions
    return _SCHEMA_TYPE_RESTRICTIONS.get(effective_type, frozenset())
