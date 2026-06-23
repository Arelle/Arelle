from __future__ import annotations

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.oim._tc.metadata import types as tc_types
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.value_validator import ValueConstraintValidator

_NAMESPACES: dict[str, str] = {"xs": XbrlConst.xsd}


def _validator(constraint_type: QName | str) -> ValueConstraintValidator:
    return ValueConstraintValidator(TCValueConstraint(str(constraint_type)), _NAMESPACES)


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
