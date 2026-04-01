from __future__ import annotations

from arelle import XbrlConst
from arelle.oim._tc.const import (
    TCME_ILLEGAL_CONSTRAINT,
    TCME_UNKNOWN_TYPE,
)
from arelle.oim._tc.metadata.common import TCMetadataValidationError
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.metadata.value_constraint_validation import (
    is_valid_constraint_type,
    validate_value_constraint,
)

_NAMESPACES: dict[str, str] = {"xs": XbrlConst.xsd}


def _errors(constraint: TCValueConstraint) -> list[TCMetadataValidationError]:
    return list(validate_value_constraint(constraint, _NAMESPACES))


class TestIsValidConstraintType:
    def test_valid_xs_string(self) -> None:
        assert is_valid_constraint_type("xs:string") is True

    def test_valid_xs_integer(self) -> None:
        assert is_valid_constraint_type("xs:integer") is True

    def test_valid_xs_date(self) -> None:
        assert is_valid_constraint_type("xs:date") is True

    def test_valid_xs_anySimpleType(self) -> None:
        assert is_valid_constraint_type("xs:anySimpleType") is True

    def test_valid_core_dimension_concept(self) -> None:
        assert is_valid_constraint_type("concept") is True

    def test_valid_core_dimension_entity(self) -> None:
        assert is_valid_constraint_type("entity") is True

    def test_valid_core_dimension_period(self) -> None:
        assert is_valid_constraint_type("period") is True

    def test_valid_core_dimension_unit(self) -> None:
        assert is_valid_constraint_type("unit") is True

    def test_valid_core_dimension_language(self) -> None:
        assert is_valid_constraint_type("language") is True

    def test_valid_decimals(self) -> None:
        assert is_valid_constraint_type("decimals") is True

    def test_invalid_xs_local_name(self) -> None:
        assert is_valid_constraint_type("xs:otherType") is False

    def test_non_xs_prefix(self) -> None:
        assert is_valid_constraint_type("nonXsPrefix:decimal") is False

    def test_trailing_whitespace(self) -> None:
        assert is_valid_constraint_type("xs:integer ") is False

    def test_leading_whitespace(self) -> None:
        assert is_valid_constraint_type(" language") is False

    def test_oim_disallowed_entity(self) -> None:
        assert is_valid_constraint_type("xs:ENTITY") is False

    def test_oim_disallowed_id(self) -> None:
        assert is_valid_constraint_type("xs:ID") is False

    def test_oim_disallowed_notation(self) -> None:
        assert is_valid_constraint_type("xs:NOTATION") is False

    def test_unknown_bare_string(self) -> None:
        assert is_valid_constraint_type("notAType") is False


class TestValidateValueConstraint:
    def test_unknown_type_yields_unknown_type_code(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:otherType"))
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_TYPE

    def test_unknown_type_path_segment_is_type(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:otherType"))
        assert errors[0].path_segments == ["type"]

    def test_unknown_type_stops_further_checks(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:bogus", length=5, total_digits=10))
        assert len(errors) == 1
        assert errors[0].code == TCME_UNKNOWN_TYPE

    def test_valid_type_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string")) == []

    def test_duration_type_on_non_duration_error(self) -> None:
        errors = _errors(TCValueConstraint(type="period", duration_type="dayTime"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT
        assert errors[0].path_segments == []

    def test_duration_type_on_duration_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:duration", duration_type="dayTime")) == []

    def test_period_type_on_non_period_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", period_type="year"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_period_type_on_period_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="period", period_type="year")) == []

    def test_time_zone_on_non_time_zoned_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", time_zone=True))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_time_zone_on_period_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="period", time_zone=False)) == []

    def test_time_zone_on_date_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:date", time_zone=True)) == []

    def test_length_on_integer_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", length=1))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_min_length_on_integer_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", min_length=1))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_max_length_on_integer_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", max_length=1))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_length_on_string_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:string", length=5)) == []

    def test_min_inclusive_on_string_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", min_inclusive="1"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_max_inclusive_on_string_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", max_inclusive="1"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_min_exclusive_on_string_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", min_exclusive="1"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_max_exclusive_on_string_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", max_exclusive="1"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_min_inclusive_invalid_value_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", min_inclusive="text"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_max_inclusive_invalid_value_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", max_inclusive="text"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_min_exclusive_invalid_value_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", min_exclusive="text"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_max_exclusive_invalid_value_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", max_exclusive="text"))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_min_inclusive_valid_value_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:integer", min_inclusive="5")) == []

    def test_min_inclusive_on_decimals_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="decimals", min_inclusive="-3")) == []

    def test_total_digits_on_string_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", total_digits=10))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_total_digits_on_decimal_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:decimal", total_digits=10)) == []

    def test_fraction_digits_on_string_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:string", fraction_digits=2))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_fraction_digits_nonzero_on_integer_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:integer", fraction_digits=1))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_fraction_digits_zero_on_integer_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:integer", fraction_digits=0)) == []

    def test_fraction_digits_on_decimal_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:decimal", fraction_digits=2)) == []

    def test_enumeration_invalid_value_for_decimal_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:decimal", enumeration_values=frozenset({"eg:Small", "eg:Medium"})))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_enumeration_invalid_value_for_int_error(self) -> None:
        errors = _errors(TCValueConstraint(type="xs:int", enumeration_values=frozenset({"NotAnInteger", "1", "2"})))
        assert len(errors) == 1
        assert errors[0].code == TCME_ILLEGAL_CONSTRAINT

    def test_enumeration_valid_values_no_error(self) -> None:
        assert _errors(TCValueConstraint(type="xs:decimal", enumeration_values=frozenset({"1.0", "2.5", "3"}))) == []
