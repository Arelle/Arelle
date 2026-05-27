from __future__ import annotations

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.restrictions import (
    DURATION_RESTRICTIONS,
    NUMERIC_RESTRICTIONS,
    ORDERED_RESTRICTIONS,
    PATTERN_AND_ENUM_RESTRICTIONS,
    PERIOD_RESTRICTIONS,
    STRING_RESTRICTIONS,
    TIME_ZONED_RESTRICTIONS,
    TCRestriction,
    get_constraint_values_by_restriction,
    permitted_restrictions,
)

_XSD_NS = XbrlConst.xsd
_EXAMPLE_NS = "http://example.com/ns"


def _xsd(local: str) -> QName:
    return QName("xs", _XSD_NS, local)


class TestPermittedRestrictionsSchemaTypes:
    @pytest.mark.parametrize(
        "local_name",
        [
            "anyURI",
            "base64Binary",
            "hexBinary",
            "language",
            "Name",
            "NCName",
            "normalizedString",
            "string",
            "token",
        ],
    )
    def test_string_like_types(self, local_name: str) -> None:
        assert permitted_restrictions(f"xs:{local_name}", _xsd(local_name)) == STRING_RESTRICTIONS

    def test_qname_only_supports_pattern_and_enumeration(self) -> None:
        assert permitted_restrictions("xs:QName", _xsd("QName")) == PATTERN_AND_ENUM_RESTRICTIONS

    @pytest.mark.parametrize(
        "local_name",
        [
            "byte",
            "decimal",
            "int",
            "integer",
            "long",
            "negativeInteger",
            "nonNegativeInteger",
            "nonPositiveInteger",
            "positiveInteger",
            "short",
            "unsignedByte",
            "unsignedInt",
            "unsignedLong",
            "unsignedShort",
        ],
    )
    def test_numeric_types(self, local_name: str) -> None:
        assert permitted_restrictions(f"xs:{local_name}", _xsd(local_name)) == NUMERIC_RESTRICTIONS

    @pytest.mark.parametrize(
        "local_name",
        [
            "date",
            "dateTime",
            "gDay",
            "gMonth",
            "gMonthDay",
            "gYear",
            "gYearMonth",
            "time",
        ],
    )
    def test_time_zoned_types(self, local_name: str) -> None:
        assert permitted_restrictions(f"xs:{local_name}", _xsd(local_name)) == TIME_ZONED_RESTRICTIONS

    @pytest.mark.parametrize(
        "local_name",
        [
            "double",
            "float",
        ],
    )
    def test_ordered_non_numeric_types(self, local_name: str) -> None:
        assert permitted_restrictions(f"xs:{local_name}", _xsd(local_name)) == ORDERED_RESTRICTIONS

    def test_duration_type(self) -> None:
        assert permitted_restrictions("xs:duration", _xsd("duration")) == DURATION_RESTRICTIONS

    def test_boolean_only_supports_pattern(self) -> None:
        assert permitted_restrictions("xs:boolean", _xsd("boolean")) == frozenset({TCRestriction.PATTERNS})

    def test_unknown_qname_returns_empty(self) -> None:
        assert permitted_restrictions("ex:custom", QName("ex", _EXAMPLE_NS, "custom")) == frozenset()

    def test_xsd_qname_not_in_table_returns_empty(self) -> None:
        assert permitted_restrictions("xs:bogusType", _xsd("bogusType")) == frozenset()


class TestPermittedRestrictionsCoreTypes:
    def test_concept(self) -> None:
        assert permitted_restrictions("concept", _xsd("QName")) == PATTERN_AND_ENUM_RESTRICTIONS

    def test_entity(self) -> None:
        assert permitted_restrictions("entity", _xsd("token")) == STRING_RESTRICTIONS

    def test_period(self) -> None:
        assert permitted_restrictions("period", _xsd("string")) == PERIOD_RESTRICTIONS

    def test_unit(self) -> None:
        assert permitted_restrictions("unit", _xsd("string")) == STRING_RESTRICTIONS

    def test_language(self) -> None:
        assert permitted_restrictions("language", _xsd("language")) == STRING_RESTRICTIONS

    def test_decimals(self) -> None:
        assert permitted_restrictions("decimals", _xsd("integer")) == NUMERIC_RESTRICTIONS


class TestGetConstraintValuesByRestriction:
    def test_includes_all_restrictions(self) -> None:
        result = get_constraint_values_by_restriction(TCValueConstraint(type="xs:string"))
        assert set(result.keys()) == set(TCRestriction)

    def test_default_constraint_returns_all_none(self) -> None:
        constraint = TCValueConstraint(type="xs:string")
        result = get_constraint_values_by_restriction(constraint)
        assert all(v is None for v in result.values())

    def test_returns_all_values(self) -> None:
        constraint = TCValueConstraint(
            type="xs:integer",
            enumeration_values=frozenset({"a", "b"}),
            patterns=frozenset({"[0-9]+"}),
            time_zone=True,
            period_type="duration",
            duration_type="yearMonthDuration",
            length=5,
            min_length=1,
            max_length=10,
            min_inclusive="0",
            max_inclusive="100",
            min_exclusive="-1",
            max_exclusive="101",
            total_digits=3,
            fraction_digits=0,
        )
        result = get_constraint_values_by_restriction(constraint)
        assert result == {
            TCRestriction.ENUMERATION_VALUES: frozenset({"a", "b"}),
            TCRestriction.PATTERNS: frozenset({"[0-9]+"}),
            TCRestriction.TIME_ZONE: True,
            TCRestriction.PERIOD_TYPE: "duration",
            TCRestriction.DURATION_TYPE: "yearMonthDuration",
            TCRestriction.LENGTH: 5,
            TCRestriction.MIN_LENGTH: 1,
            TCRestriction.MAX_LENGTH: 10,
            TCRestriction.MIN_INCLUSIVE: "0",
            TCRestriction.MAX_INCLUSIVE: "100",
            TCRestriction.MIN_EXCLUSIVE: "-1",
            TCRestriction.MAX_EXCLUSIVE: "101",
            TCRestriction.TOTAL_DIGITS: 3,
            TCRestriction.FRACTION_DIGITS: 0,
        }

    def test_mixed_set_and_unset_values(self) -> None:
        constraint = TCValueConstraint(
            type="xs:string",
            patterns=frozenset({"[a-z]+"}),
            min_length=3,
            max_length=10,
        )
        result = get_constraint_values_by_restriction(constraint)
        assert result == {
            TCRestriction.PATTERNS: frozenset({"[a-z]+"}),
            TCRestriction.MIN_LENGTH: 3,
            TCRestriction.MAX_LENGTH: 10,
            TCRestriction.ENUMERATION_VALUES: None,
            TCRestriction.TIME_ZONE: None,
            TCRestriction.PERIOD_TYPE: None,
            TCRestriction.DURATION_TYPE: None,
            TCRestriction.LENGTH: None,
            TCRestriction.MIN_INCLUSIVE: None,
            TCRestriction.MAX_INCLUSIVE: None,
            TCRestriction.MIN_EXCLUSIVE: None,
            TCRestriction.MAX_EXCLUSIVE: None,
            TCRestriction.TOTAL_DIGITS: None,
            TCRestriction.FRACTION_DIGITS: None,
        }
