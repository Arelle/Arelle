from __future__ import annotations

import pytest

from arelle import XbrlConst
from arelle.oim._tc.const import (
    TCME_ILLEGAL_CONSTRAINT,
    TCME_UNKNOWN_DURATION_TYPE,
    TCME_UNKNOWN_PERIOD_TYPE,
    TCME_UNKNOWN_TYPE,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.value_constraint_validation import validate_value_constraint

_NAMESPACES: dict[str, str] = {"xs": XbrlConst.xsd}


def _errors(constraint: TCValueConstraint) -> list[TCMetadataValidationError]:
    return list(validate_value_constraint(constraint, _NAMESPACES))


class TestValidateValueConstraint:
    def test_unknown_type_yields_unknown_type_code(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:otherType"))
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_TYPE
        assert errors[0].json_pointers == ["/type"]

    def test_valid_type_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string")) == []

    def test_valid_type_with_permitted_restriction_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", length=10)) == []

    def test_valid_type_with_all_permitted_restrictions_no_error(self) -> None:
        assert (
            _errors(
                TCValueConstraint(
                    type="xs:decimal",
                    total_digits=10,
                    fraction_digits=2,
                    min_inclusive="0",
                    max_inclusive="100",
                    patterns=frozenset({"\\d+"}),
                    enumeration_values=frozenset({"1", "2"}),
                )
            )
            == []
        )

    def test_disallowed_restriction_yields_illegal_constraint_code(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", total_digits=5))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/totalDigits"]

    def test_multiple_disallowed_restrictions(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", total_digits=5, fraction_digits=2))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/fractionDigits", "/totalDigits"]

    def test_boolean_disallows_length(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:boolean", length=1))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/length"]

    def test_boolean_permits_patterns(self) -> None:
        assert _errors(TCValueConstraint(type="xs:boolean", patterns=frozenset({"true|false"}))) == []

    def test_date_disallows_length_and_digits(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:date", length=10, total_digits=5))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/length", "/totalDigits"]

    def test_date_permits_bounds(self) -> None:
        assert _errors(TCValueConstraint(type="xs:date", min_inclusive="2020-01-01")) == []

    def test_time_zone_permitted_on_period(self) -> None:
        assert _errors(TCValueConstraint(type="period", time_zone=True)) == []

    def test_time_zone_permitted_on_date_time(self) -> None:
        assert _errors(TCValueConstraint(type="xs:dateTime", time_zone=True)) == []

    def test_time_zone_disallowed_on_string(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", time_zone=True))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/timeZone"]

    @pytest.mark.parametrize("period_type", ["year", "half", "quarter", "week", "month", "day", "instant"])
    def test_valid_period_type_no_error(self, period_type: str) -> None:
        assert _errors(TCValueConstraint(type="period", period_type=period_type)) == []

    def test_unknown_period_type_error(self) -> None:
        errors = _errors(TCValueConstraint(type="period", period_type="biweekly"))
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_PERIOD_TYPE
        assert errors[0].json_pointers == ["/periodType"]

    def test_period_type_disallowed_on_string(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", period_type="year"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/periodType"]

    @pytest.mark.parametrize("duration_type", ["yearMonth", "dayTime"])
    def test_valid_duration_type_no_error(self, duration_type: str) -> None:
        assert _errors(TCValueConstraint(type="xs:duration", duration_type=duration_type)) == []

    def test_unknown_duration_type_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:duration", duration_type="P1Y"))
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_DURATION_TYPE
        assert errors[0].json_pointers == ["/durationType"]

    def test_duration_type_disallowed_on_string(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", duration_type="yearMonth"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/durationType"]

    def test_duration_type_disallowed_on_period(self) -> None:
        errors = _errors(TCValueConstraint(type="period", duration_type="yearMonth"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/durationType"]

    def test_patterns_single_valid_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", patterns=frozenset({r"[a-z]+"}))) == []

    def test_patterns_multiple_valid_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", patterns=frozenset({r"[a-z]+", r"\d{3}-\d{4}"}))) == []

    def test_patterns_invalid_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", patterns=frozenset({"["})))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/patterns"]

    def test_patterns_mixed_reports_only_invalid(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", patterns=frozenset({r"[a-z]+", "(", r"\d+", "["})))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert str(errors[0]) == "/patterns: Patterns ['(', '['] are not valid XSD regular expressions"
        assert errors[0].json_pointers == ["/patterns"]

    def test_patterns_xsd_name_char_escapes_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", patterns=frozenset({r"\i\c*"}))) == []

    def test_patterns_unicode_category_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", patterns=frozenset({r"\p{L}+"}))) == []

    def test_patterns_lookahead_rejected(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", patterns=frozenset({"foo(?=bar)"})))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/patterns"]

    def test_patterns_non_capturing_group_rejected(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", patterns=frozenset({"(?:foo)"})))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/patterns"]

    def test_patterns_escaped_paren_with_quantifier_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", patterns=frozenset({r"\(?"}))) == []

    def test_length_with_min_length_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", length=5, min_length=5))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/length", "/minLength"]

    def test_length_with_max_length_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", length=5, max_length=5))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/length", "/maxLength"]

    def test_length_with_both_min_and_max_length_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", length=5, min_length=3, max_length=10))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/length", "/minLength", "/maxLength"]

    def test_min_length_greater_than_max_length_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", min_length=10, max_length=5))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minLength", "/maxLength"]

    def test_min_and_max_length_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", min_length=2, max_length=10)) == []

    def test_min_length_equal_max_length_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", min_length=5, max_length=5)) == []


class TestBoundsFacets:
    @pytest.mark.parametrize(
        "xs_type, value",
        [
            ("xs:decimal", "1"),
            ("xs:integer", "1"),
            ("xs:date", "2024-01-01"),
            ("xs:dateTime", "2024-01-01T00:00:00"),
            ("xs:time", "12:00:00"),
            ("xs:gYear", "2024"),
            ("xs:duration", "P1D"),
        ],
    )
    def test_min_inclusive_alone_no_error_on_permitted_types(self, xs_type: str, value: str) -> None:
        assert _errors(TCValueConstraint(type=xs_type, min_inclusive=value)) == []

    @pytest.mark.parametrize(
        "xs_type",
        ["xs:string", "xs:Name", "xs:NCName", "xs:hexBinary", "xs:QName", "xs:boolean"],
    )
    def test_bounds_on_non_permitted_types_error(self, xs_type: str) -> None:
        errors = _errors(TCValueConstraint(type=xs_type, min_inclusive="x"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/minInclusive"]

    def test_all_bounds_on_non_permitted_type(self) -> None:
        errors = _errors(
            TCValueConstraint(
                type="xs:string",
                min_inclusive="a",
                max_inclusive="b",
                min_exclusive="c",
                max_exclusive="d",
            )
        )
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/type", "/maxExclusive", "/maxInclusive", "/minExclusive", "/minInclusive"]

    def test_min_inclusive_with_min_exclusive_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", min_inclusive="1", min_exclusive="1"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minInclusive", "/minExclusive"]

    def test_max_inclusive_with_max_exclusive_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", max_inclusive="1", max_exclusive="1"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/maxInclusive", "/maxExclusive"]

    def test_min_inclusive_greater_than_max_inclusive_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", min_inclusive="10", max_inclusive="5"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minInclusive", "/maxInclusive"]

    def test_min_inclusive_equal_max_inclusive_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:decimal", min_inclusive="5", max_inclusive="5")) == []

    def test_min_inclusive_equal_max_exclusive_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", min_inclusive="5", max_exclusive="5"))
        assert len(errors) == 1
        assert errors[0].json_pointers == ["/minInclusive", "/maxExclusive"]

    def test_min_exclusive_equal_max_inclusive_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", min_exclusive="5", max_inclusive="5"))
        assert len(errors) == 1
        assert errors[0].json_pointers == ["/minExclusive", "/maxInclusive"]

    def test_min_exclusive_equal_max_exclusive_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:decimal", min_exclusive="5", max_exclusive="5")) == []

    def test_min_exclusive_greater_than_max_exclusive_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", min_exclusive="10", max_exclusive="5"))
        assert len(errors) == 1
        assert errors[0].json_pointers == ["/minExclusive", "/maxExclusive"]

    def test_date_ordering_violation(self) -> None:
        errors = _errors(
            TCValueConstraint(
                type="xs:date",
                min_inclusive="2024-12-31",
                max_inclusive="2024-01-01",
            )
        )
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minInclusive", "/maxInclusive"]

    def test_date_ordering_valid(self) -> None:
        assert (
            _errors(
                TCValueConstraint(
                    type="xs:date",
                    min_inclusive="2024-01-01",
                    max_inclusive="2024-12-31",
                )
            )
            == []
        )

    def test_g_year_ordering_violation(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:gYear", min_inclusive="2030", max_inclusive="2020"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minInclusive", "/maxInclusive"]

    def test_duration_ordering_violation(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:duration", min_exclusive="P10D", max_exclusive="P1D"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minExclusive", "/maxExclusive"]

    def test_unparseable_bound_yields_error_and_skips_ordering(self) -> None:
        errors = _errors(
            TCValueConstraint(
                type="xs:decimal",
                min_inclusive="seven",
                max_inclusive="1",
            )
        )
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].json_pointers == ["/minInclusive"]

    @pytest.mark.parametrize(
        "facet_kwarg",
        [
            {"min_inclusive": "one"},
            {"max_inclusive": "one"},
            {"min_exclusive": "one"},
            {"max_exclusive": "one"},
        ],
    )
    def test_each_unparseable_bound_facet_yields_error(self, facet_kwarg: dict[str, str]) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", **facet_kwarg))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_mutex_still_fires_when_value_unparseable(self) -> None:
        errors = _errors(
            TCValueConstraint(
                type="xs:decimal",
                min_inclusive="bogus",
                min_exclusive="alsoBogus",
            )
        )
        assert len(errors) == 3
        assert all(e.code == TCME_ILLEGAL_CONSTRAINT for e in errors)
        assert errors[0].json_pointers == ["/minInclusive", "/minExclusive"]
        assert errors[1].json_pointers == ["/minInclusive"]
        assert errors[2].json_pointers == ["/minExclusive"]
