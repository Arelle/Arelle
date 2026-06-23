from __future__ import annotations

from collections.abc import Mapping

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.oim._tc.metadata import types as tc_types
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.value_validator import ValueConstraintValidator

_NAMESPACES: dict[str, str] = {"xs": XbrlConst.xsd}


def _validator(
    constraint_type: QName | str,
    namespaces: Mapping[str, str] = _NAMESPACES,
    **kwargs: object,
) -> ValueConstraintValidator:
    return ValueConstraintValidator(TCValueConstraint(str(constraint_type), **kwargs), namespaces)


class TestValidateUnknownType:
    def test_unknown_type_validation(self) -> None:
        assert _validator("unknown:type").validate("anything") is False


class TestValidateString:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("hello", True),
            ("", True),
        ],
    )
    def test_string_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.STRING).validate(value) is expected


class TestValidateDecimal:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("1", True),
            ("2.5", True),
            ("abc", False),
        ],
    )
    def test_decimal_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.DECIMAL).validate(value) is expected


class TestValidateInteger:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("1", True),
            ("1.5", False),
        ],
    )
    def test_integer_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.INTEGER).validate(value) is expected


class TestValidateDate:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("2020-01-01", True),
            ("not-a-date", False),
        ],
    )
    def test_date_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.DATE).validate(value) is expected


class TestValidateGMonthDay:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("--01-01", True),
            ("--07-04", True),
            ("01-01", False),
        ],
    )
    def test_g_month_day_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.G_MONTH_DAY).validate(value) is expected


class TestValidateBoolean:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("true", True),
            ("false", True),
            ("1", True),
            ("0", True),
            ("yes", False),
        ],
    )
    def test_boolean_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.BOOLEAN).validate(value) is expected


class TestValidateQName:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("xs:string", True),
            ("not a qname!", False),
        ],
    )
    def test_qname_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.QNAME).validate(value) is expected


class TestValidateWithFacets:
    def test_length_valid(self) -> None:
        assert _validator(tc_types.STRING, length=3).validate("abc") is True

    def test_length_invalid(self) -> None:
        assert _validator(tc_types.STRING, length=3).validate("abcd") is False

    def test_max_length_valid(self) -> None:
        assert _validator(tc_types.STRING, max_length=3).validate("abc") is True

    def test_max_length_invalid(self) -> None:
        assert _validator(tc_types.STRING, max_length=3).validate("abcde") is False

    def test_min_length_valid(self) -> None:
        assert _validator(tc_types.STRING, min_length=2).validate("ab") is True

    def test_min_length_invalid(self) -> None:
        assert _validator(tc_types.STRING, min_length=2).validate("a") is False

    def test_min_inclusive_valid(self) -> None:
        assert _validator(tc_types.DECIMAL, min_inclusive="100").validate("100") is True

    def test_min_inclusive_invalid(self) -> None:
        assert _validator(tc_types.DECIMAL, min_inclusive="100").validate("50") is False

    def test_max_inclusive_valid(self) -> None:
        assert _validator(tc_types.DECIMAL, max_inclusive="100").validate("100") is True

    def test_max_inclusive_invalid(self) -> None:
        assert _validator(tc_types.DECIMAL, max_inclusive="100").validate("150") is False

    def test_fraction_digits_valid(self) -> None:
        assert _validator(tc_types.DECIMAL, fraction_digits=2).validate("1.23") is True

    def test_fraction_digits_invalid(self) -> None:
        assert _validator(tc_types.DECIMAL, fraction_digits=2).validate("1.234") is False

    def test_multiple_patterns_any_match(self) -> None:
        assert _validator(tc_types.STRING, patterns=frozenset({"[a-z]+", "[A-Z]+"})).validate("ABC") is True

    def test_multiple_facets_all_satisfied(self) -> None:
        assert _validator(tc_types.STRING, length=3, patterns=frozenset({"[a-z]+"})).validate("abc") is True

    def test_min_exclusive_valid(self) -> None:
        assert _validator(tc_types.DECIMAL, min_exclusive="100").validate("101") is True

    def test_min_exclusive_invalid(self) -> None:
        assert _validator(tc_types.DECIMAL, min_exclusive="100").validate("100") is False

    def test_max_exclusive_valid(self) -> None:
        assert _validator(tc_types.DECIMAL, max_exclusive="100").validate("99") is True

    def test_max_exclusive_invalid(self) -> None:
        assert _validator(tc_types.DECIMAL, max_exclusive="100").validate("100") is False

    def test_total_digits_valid(self) -> None:
        assert _validator(tc_types.DECIMAL, total_digits=3).validate("123") is True

    def test_total_digits_invalid(self) -> None:
        assert _validator(tc_types.DECIMAL, total_digits=3).validate("1234") is False

    def test_multiple_facets_one_violated(self) -> None:
        assert _validator(tc_types.STRING, length=3, patterns=frozenset({"[a-z]+"})).validate("abcd") is False
