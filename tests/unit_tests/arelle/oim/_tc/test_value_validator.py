from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import pytest

from arelle import XbrlConst
from arelle.ModelValue import QName
from arelle.oim._tc.metadata import types as tc_types
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.value_validator import ValueConstraintValidator

_NAMESPACES = MappingProxyType({"xs": XbrlConst.xsd})
_UNIT_NAMESPACES = MappingProxyType(
    {
        **_NAMESPACES,
        "iso4217": "http://www.xbrl.org/2003/iso4217",
        "scheme": "http://example.com/scheme",
    }
)


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


class TestValidateConcept:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("xs:string", True),
            ("localName", False),
            ("bad:not a qname!", False),
            ("", False),
        ],
    )
    def test_concept_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.CORE_CONCEPT).validate(value) is expected


class TestValidateLanguage:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("en", True),
            ("en-us", True),
            ("en-x-twain", True),
            ("he-il-u-ca-hebrew-tz-jeruslm", True),
            ("zh-hans", True),
            ("x-private", True),
            ("i-klingon", True),
            ("abcdefgh", True),
            ("en-US", False),
            ("EN", False),
            ("EN-US", False),
            ("he-IL-u-ca-hebrew-tz-jeruslm", False),
            ("zh-Hant", False),
            (" hello", False),
            ("hello ", False),
            ("", False),
        ],
    )
    def test_language_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.CORE_LANGUAGE).validate(value) is expected


class TestValidateEntity:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("xs:entity", True),
            ("xs:entity with space", False),
            ("unprefixed", False),
            ("unknown:entity", False),
            ("", False),
        ],
    )
    def test_entity_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.CORE_ENTITY).validate(value) is expected


class TestValidatePeriod:
    @pytest.mark.parametrize(
        "value, expected",
        [
            # Valid: years
            ("2024", True),
            ("2024@end", True),
            # Valid: year-months
            ("2024-12", True),
            # Valid: quarters
            ("2024Q1", True),
            ("2024Q4", True),
            ("2024Q1@start", True),
            # Valid: halves
            ("2024H1", True),
            ("2024H2", True),
            # Valid: weeks
            ("2024W01", True),
            ("2020W53", True),
            ("2026W53", True),
            ("2024W29@end", True),
            # Valid: single dates
            ("2024-01-01", True),
            ("2024-02-29", True),
            # Valid: datetime instants
            ("2024-01-02T00:00:00", True),
            ("2024-06-15T12:00:00Z", True),
            ("2024-01-01T00:00:00+05:00", True),
            # Valid: date ranges
            ("2024-01-01..2024-12-31", True),
            ("2024-01-01..2024-01-01", True),
            # Valid: explicit durations
            ("2024-01-01T00:00:00/2025-01-01T00:00:00", True),
            # Invalid: empty
            ("", False),
            # Invalid: year zero
            ("0000", False),
            ("0000-01-01", False),
            ("0000-01-01T00:00:00", False),
            ("0000H1", False),
            ("0000Q1", False),
            ("0000W01", False),
            ("0000-01", False),
            ("0000-01-01..0000-12-31", False),
            ("0000-01-01T00:00:00/0001-01-01T00:00:00", False),
            # Invalid: plus sign
            ("+12024", False),
            ("+12024-01", False),
            ("+12024-01-01", False),
            ("+12024-01-01T00:00:00", False),
            ("+12024H1", False),
            ("+12024Q1", False),
            ("+12024W01", False),
            # Invalid: T24 hour
            ("2024-01-01T24:00:00", False),
            ("2024-02-29T24:00:00", False),
            ("2024-02-28T24:00:00", False),
            ("2024-01-01T24:00:01", False),
            # Invalid: fractional seconds
            ("2024-01-01T00:00:00.0", False),
            ("2024-01-01T00:00:00.000", False),
            ("2024-06-15T12:00:00.000Z", False),
            # Invalid: timezone offset (TC only allows Z)
            ("2024-01-01T00:00:00+00:00", False),
            # Invalid: timezone on non-datetime
            ("2024-02-29Z", False),
            ("2024Z", False),
            # Invalid: leap day in non-leap year
            ("2025-02-29", False),
            # Invalid: bare time
            ("00:00:00", False),
            # Invalid: missing leading zeros
            ("2024-01-1", False),
            ("2024-1-01", False),
            # Invalid: out of range
            ("2024-13-01", False),
            ("2024-00", False),
            ("2024-13", False),
            ("2024-1", False),
            # Invalid: duration format
            ("P1Y2M3DT4H5M6S", False),
            # Invalid: bare suffix
            ("@end", False),
            # Invalid: date range violations
            ("2024-12-31..2024-01-01", False),
            ("2024-01-01..2024-12-31@end", False),
            ("2024-01-01..2024-12", False),
            ("2024-01..2024-12", False),
            ("2024..2025", False),
            ("2024-01-01..2024-12-1", False),
            ("2024-1-01..2024-12-31", False),
            # Invalid: explicit duration violations
            ("2025-01-01T00:00:00/2024-01-01T00:00:00", False),
            ("2024-01-01T00:00:00/2024-01-01T00:00:00", False),
            ("2024-01-01T00:00:00/2025-01-01T00:00:00@end", False),
            ("2024-06-15T12:00:00Z@end", False),
            # Invalid: half/quarter/week values
            ("2024H0", False),
            ("2024H3", False),
            ("2024Q0", False),
            ("2024Q5", False),
            ("2024W00", False),
            ("2024W54", False),
            ("2024W53", False),
            ("2025W53", False),
            ("2024W1", False),
        ],
    )
    def test_period_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.CORE_PERIOD).validate(value) is expected


class TestValidatePeriodType:
    @pytest.mark.parametrize(
        "period_type, value, expected",
        [
            ("year", "2024", True),
            ("year", "2024@end", True),
            ("year", "2024Q1", False),
            ("year", "2024-01", False),
            ("half", "2024H1", True),
            ("half", "2024", False),
            ("quarter", "2024Q1", True),
            ("quarter", "2024", False),
            ("week", "2024W29", True),
            ("week", "2024", False),
            ("month", "2024-01", True),
            ("month", "2024", False),
            ("day", "2024-01-01", True),
            ("day", "2024", False),
            ("instant", "2024-01-01T00:00:00", True),
            ("instant", "2024Q1@end", True),
            ("instant", "2024Q1", False),
        ],
    )
    def test_period_type_validation(self, period_type: str, value: str, expected: bool) -> None:
        assert _validator(tc_types.CORE_PERIOD, period_type=period_type).validate(value) is expected


class TestValidateDurationType:
    @pytest.mark.parametrize(
        "duration_type, value, expected",
        [
            # yearMonth: only year and month components
            ("yearMonth", "P1Y", True),
            ("yearMonth", "P1M", True),
            ("yearMonth", "P1Y2M", True),
            ("yearMonth", "P1Y2M3D", False),
            ("yearMonth", "P1Y2M3DT4H5M6S", False),
            ("yearMonth", "PT1H", False),
            ("yearMonth", "P1D", False),
            # dayTime: only day, hour, minute, second components
            ("dayTime", "P1D", True),
            ("dayTime", "PT1H", True),
            ("dayTime", "PT1M", True),
            ("dayTime", "PT1S", True),
            ("dayTime", "P1DT2H3M4S", True),
            ("dayTime", "P1Y", False),
            ("dayTime", "P1M", False),
            ("dayTime", "P1Y2M3DT4H5M6S", False),
        ],
    )
    def test_duration_type_validation(self, duration_type: str, value: str, expected: bool) -> None:
        assert _validator(tc_types.DURATION, duration_type=duration_type).validate(value) is expected


class TestValidateUnit:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("iso4217:USD", True),
            ("iso4217:EUR*iso4217:USD", True),
            ("iso4217:USD/scheme:m", True),
            ("(iso4217:EUR*iso4217:USD)/scheme:m", True),
            ("iso4217:USD/(scheme:m*scheme:s)", True),
            ("(iso4217:EUR*iso4217:USD)/(scheme:m*scheme:s)", True),
            ("iso4217:USD*iso4217:USD", True),
            ("", False),
            ("localOnly", False),
            ("undef:foo", False),
            ("scheme:m*iso4217:USD", False),
            ("iso4217:USD/(scheme:s*iso4217:m)", False),
            ("*iso4217:USD", False),
            ("iso4217:USD*", False),
            ("iso4217:USD/scheme:m/scheme:s", False),
            ("iso4217:USD / scheme:m", False),
            ("iso4217:EUR*iso4217:USD/scheme:m", False),
            ("iso4217:USD/scheme:m*scheme:s", False),
            ("/scheme:m", False),
            ("(iso4217:USD)/scheme:m", False),
            ("iso4217:USD ", False),
        ],
    )
    def test_unit_validation(self, value: str, expected: bool) -> None:
        assert _validator(tc_types.CORE_UNIT, _UNIT_NAMESPACES).validate(value) is expected


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

    def test_pattern_valid(self) -> None:
        assert _validator(tc_types.STRING, patterns=frozenset({"[a-z]+"})).validate("abc") is True

    def test_pattern_invalid(self) -> None:
        assert _validator(tc_types.STRING, patterns=frozenset({"[a-z]+"})).validate("ABC") is False

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
