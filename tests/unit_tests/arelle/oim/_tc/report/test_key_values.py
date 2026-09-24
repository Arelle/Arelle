from __future__ import annotations

from types import MappingProxyType

import pytest

from arelle import XbrlConst
from arelle.oim._tc.metadata.model import TCValueConstraint
from arelle.oim._tc.report.key_values import NULL_KEY_VALUE, KeyFieldType, KeyValue

_NAMESPACES = MappingProxyType({"xs": XbrlConst.xsd, "eg": "http://example.com/eg"})


def _key_value(
    constraint_type: str, value: str | None, duration_type: str | None = None
) -> KeyValue:
    constraint = TCValueConstraint(constraint_type, duration_type=duration_type)
    return KeyFieldType(constraint, _NAMESPACES).key_value(value)


class TestEquality:
    @pytest.mark.parametrize(
        "constraint_type, first, second",
        [
            ("xs:integer", "01", "1"),
            ("xs:integer", "-0", "0"),
            ("xs:integer", "+1", "1"),
            ("decimals", "02", "2"),
            ("xs:decimal", "1.0", "1"),
            ("xs:decimal", ".5", "0.50"),
            ("xs:boolean", "0", "false"),
            ("xs:boolean", "1", "true"),
            ("xs:token", " a  b ", "a b"),
            ("xs:normalizedString", "a\tb", "a b"),
            ("xs:QName", " eg:a ", "eg:a"),
            ("entity", "eg:a ", "eg:a"),
            ("xs:date", "2024-01-01Z", "2024-01-01+00:00"),
            ("xs:dateTime", "2024-01-01T00:00:00+01:00", "2023-12-31T23:00:00Z"),
            ("xs:dateTime", "2024-01-01T24:00:00Z", "2024-01-02T00:00:00Z"),
            ("xs:dateTime", "2024-01-01T12:00:00Z", "2024-01-01T13:00:00+01:00"),
            ("xs:gYear", "12024", "12024"),
            ("xs:gYearMonth", "-12024-01", "-12024-01"),
            ("xs:gMonthDay", "--12-25Z", "--12-25+00:00"),
            ("xs:gDay", "---05", "---05"),
            ("xs:gMonth", "--12", "--12"),
            ("xs:time", "12:00:00", "12:00:00.0"),
            ("xs:time", "24:00:00", "00:00:00"),
            ("xs:time", "12:00:00Z", "13:00:00+01:00"),
            ("xs:time", "00:00:00+01:00", "23:00:00Z"),
            ("xs:time", "23:30:00-01:00", "00:30:00Z"),
            ("period", "2024", "2024-01-01T00:00:00/2025-01-01T00:00:00"),
            ("period", "2024-01-01", "2024-01-01..2024-01-01"),
            ("period", "2024-01-01..2024-01-31", "2024-01"),
            ("period", "2024@end", "2025-01-01T00:00:00"),
        ],
    )
    def test_lexical_forms_of_one_value_are_equal(
        self, constraint_type: str, first: str, second: str
    ) -> None:
        assert _key_value(constraint_type, first) == _key_value(constraint_type, second)

    @pytest.mark.parametrize(
        "duration_type, first, second",
        [
            ("yearMonth", "P1Y", "P12M"),
            ("yearMonth", "-P1Y", "-P12M"),
            ("dayTime", "P1D", "PT24H"),
            ("dayTime", "PT1H", "PT60M"),
            ("dayTime", "PT1M", "PT60S"),
            ("dayTime", "PT0.5S", "PT0.50S"),
        ],
    )
    def test_durations_are_equal_by_length(
        self, duration_type: str, first: str, second: str
    ) -> None:
        assert _key_value(
            "xs:duration", first, duration_type=duration_type
        ) == _key_value("xs:duration", second, duration_type=duration_type)

    @pytest.mark.parametrize(
        "constraint_type, first, second",
        [
            ("xs:string", " a", "a"),
            ("xs:string", "", " "),
            ("xs:integer", "1", "2"),
            ("xs:decimal", "1.0", "1.01"),
            ("xs:boolean", "true", "false"),
            ("xs:QName", "eg:a", "xs:a"),
            ("xs:date", "2024-01-01", "2024-01-02"),
            ("xs:date", "2024-01-01", "2024-01-01Z"),
            ("xs:time", "12:00:00", "12:00:01"),
            ("period", "2024", "2024@start"),
            ("period", "2024-01-01..2024-01-30", "2024-01"),
        ],
    )
    def test_different_values_are_not_equal(
        self, constraint_type: str, first: str, second: str
    ) -> None:
        assert _key_value(constraint_type, first) != _key_value(constraint_type, second)

    def test_null_is_equal_to_null_and_nothing_else(self) -> None:
        assert _key_value("xs:string", None) == NULL_KEY_VALUE
        assert _key_value("xs:integer", None) == NULL_KEY_VALUE
        assert _key_value("xs:string", "") != NULL_KEY_VALUE

    def test_integer_beyond_the_int_conversion_limit_is_a_typed_value(self) -> None:
        digits = "1" * 5000
        assert _key_value("xs:integer", "0" + digits) == _key_value("xs:integer", digits)
        assert _key_value("xs:integer", digits) != _key_value("xs:integer", "1")

    def test_invalid_values_are_equal_by_literal_only(self) -> None:
        assert _key_value("xs:integer", "x") == _key_value("xs:integer", "x")
        assert _key_value("xs:integer", "x") != _key_value("xs:integer", "y")
        assert _key_value("xs:integer", "1") != _key_value("xs:string", "1")


class TestOrdering:
    @pytest.mark.parametrize(
        "constraint_type, ordered",
        [
            ("xs:integer", ["-1", "0", "1", "10"]),
            ("xs:decimal", ["-0.5", "0", "0.25", "1.5"]),
            ("xs:boolean", ["false", "true"]),
            ("xs:string", ["Zoo", "abc", "Ä", "á", "！"]),
            ("xs:date", ["-12024-01-01", "2024-01-01", "12024-01-01"]),
            ("xs:dateTime", ["2024-01-01T00:00:00Z", "2024-01-01T00:00:01Z"]),
            ("xs:time", ["00:00:00", "12:00:00", "23:59:59"]),
            ("xs:gMonthDay", ["--01-31", "--02-01"]),
            ("period", ["2021-01-01@start", "2021-01-01", "2021", "2021-06"]),
        ],
    )
    def test_values_order_by_type(
        self, constraint_type: str, ordered: list[str]
    ) -> None:
        key_values = [_key_value(constraint_type, value) for value in ordered]
        assert key_values == sorted(key_values)
        assert len(set(key_values)) == len(key_values)

    def test_durations_order_by_length(self) -> None:
        ordered = ["-P1DT1H", "PT0S", "PT1M", "PT60.5S", "P1D"]
        key_values = [
            _key_value("xs:duration", value, duration_type="dayTime")
            for value in ordered
        ]
        assert key_values == sorted(key_values)

    def test_null_sorts_before_values_and_invalid_after(self) -> None:
        null = _key_value("xs:integer", None)
        value = _key_value("xs:integer", "1")
        invalid = _key_value("xs:integer", "x")
        assert null < value < invalid
