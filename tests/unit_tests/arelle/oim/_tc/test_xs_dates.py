from __future__ import annotations

import datetime
from collections.abc import Callable
from decimal import Decimal

import pytest

from arelle.oim._tc.xs_dates import (
    XsInstant,
    days_since_epoch,
    parse_date,
    parse_date_time,
    parse_g_year,
    parse_g_day,
    parse_g_month,
    parse_g_month_day,
    parse_g_year_month,
    parse_time,
    year_number,
)

_EPOCH = datetime.date(1970, 1, 1)


def _day(parser: Callable[[str], XsInstant | None], value: str) -> int:
    instant = parser(value)
    assert instant is not None
    return instant.day


class TestDaysSinceEpoch:
    @pytest.mark.parametrize(
        "date",
        [
            datetime.date(1, 1, 1),
            datetime.date(1600, 2, 29),
            datetime.date(1900, 3, 1),
            datetime.date(1969, 12, 31),
            datetime.date(1970, 1, 1),
            datetime.date(2000, 2, 29),
            datetime.date(2024, 2, 29),
            datetime.date(9999, 12, 31),
        ],
    )
    def test_matches_datetime(self, date: datetime.date) -> None:
        assert days_since_epoch(date.year, date.month, date.day) == (date - _EPOCH).days

    def test_matches_datetime_across_a_span_of_days(self) -> None:
        date = datetime.date(1896, 1, 1)
        while date.year < 1906:
            assert days_since_epoch(date.year, date.month, date.day) == (date - _EPOCH).days
            date += datetime.timedelta(days=1)

    def test_years_beyond_datetime_continue_the_cycle(self) -> None:
        # 400 Gregorian years are exactly 146097 days, so shifting by 400 years is exact.
        assert days_since_epoch(12024, 1, 1) == days_since_epoch(2024, 1, 1) + 25 * 146097
        assert days_since_epoch(-2376, 1, 1) == days_since_epoch(2024, 1, 1) - 11 * 146097
        assert days_since_epoch(0, 1, 1) == days_since_epoch(400, 1, 1) - 146097


class TestParseDate:
    def test_parses_in_range_date(self) -> None:
        assert parse_date("2024-02-29") == XsInstant(day=(datetime.date(2024, 2, 29) - _EPOCH).days, second=Decimal(0), zoned=False)

    def test_parses_wide_and_negative_years(self) -> None:
        assert parse_date("12024-01-01") is not None
        assert parse_date("-12024-01-01") is not None
        assert parse_date("-0001-01-01") is not None

    @pytest.mark.parametrize(
        "value",
        [
            "0000-01-01",
            "+2024-01-01",
            "2024-1-01",
            "2024-13-01",
            "2024-02-30",
            "2023-02-29",
            "2024-01-01T00:00:00",
            "2024-01-01+14:01",
            "2024-01-01Z ",
            " 2024-01-01",
            "12024-01-01Q",
        ],
    )
    def test_rejects_invalid_lexical_values(self, value: str) -> None:
        assert parse_date(value) is None

    def test_time_zone_normalises_to_utc(self) -> None:
        assert parse_date("2024-01-01Z") == parse_date("2024-01-01+00:00")
        assert parse_date("2024-01-01+05:00") == parse_date_time("2023-12-31T19:00:00Z")
        assert parse_date("2024-01-01-05:00") == parse_date_time("2024-01-01T05:00:00Z")

    def test_zoned_and_unzoned_are_not_equal(self) -> None:
        assert parse_date("2024-01-01Z") != parse_date("2024-01-01")


class TestParseDateTime:
    def test_fractional_seconds_are_exact(self) -> None:
        assert parse_date_time("2024-01-01T12:00:00.5") == parse_date_time("2024-01-01T12:00:00.50")
        assert parse_date_time("2024-01-01T12:00:00.1") != parse_date_time("2024-01-01T12:00:00.10000001")

    def test_fractional_seconds_beyond_28_digits_stay_distinct(self) -> None:
        first = parse_date_time("2024-01-01T00:00:01.0000000000000000000000000001Z")
        second = parse_date_time("2024-01-01T00:00:01.0000000000000000000000000002Z")
        assert first != second

    def test_end_of_day_rolls_over(self) -> None:
        assert parse_date_time("2024-01-01T24:00:00") == parse_date_time("2024-01-02T00:00:00")
        assert parse_date_time("2024-12-31T24:00:00Z") == parse_date_time("2025-01-01T00:00:00Z")

    def test_leap_second_rolls_into_the_next_minute(self) -> None:
        assert parse_date_time("2016-12-31T23:59:60Z") == parse_date_time("2017-01-01T00:00:00Z")
        assert parse_date_time("2016-12-31T23:59:60.5Z") == parse_date_time("2017-01-01T00:00:00.5Z")
        assert parse_date_time("2016-06-30T12:29:60") == parse_date_time("2016-06-30T12:30:00")
        assert parse_date_time("2016-12-31T23:59:60-01:00") == parse_date_time("2017-01-01T01:00:00Z")

    @pytest.mark.parametrize(
        "value",
        [
            "2024-01-01T24:00:01",
            "2024-01-01T24:01:00",
            "2024-01-01T25:00:00",
            "2024-01-01T12:60:00",
            "2024-01-01T12:00:61",
            "2024-01-01T24:00:60",
        ],
    )
    def test_rejects_invalid_times(self, value: str) -> None:
        assert parse_date_time(value) is None

    def test_negative_time_zone_offset_crosses_year_boundary(self) -> None:
        assert parse_date_time("-12024-01-01T00:00:00+01:00") == parse_date_time("-12025-12-31T23:00:00Z")


class TestBceYears:
    """XSD 1.0 has no year zero, so -0001 is 1 BCE and immediately precedes 0001."""

    @pytest.mark.parametrize(("lexical_year", "expected"), [("2024", 2024), ("0001", 1), ("-0001", 0), ("-12024", -12023)])
    def test_year_number(self, lexical_year: str, expected: int) -> None:
        assert year_number(lexical_year) == expected

    def test_end_of_1_bce_is_start_of_1_ce(self) -> None:
        assert parse_date_time("-0001-12-31T24:00:00") == parse_date_time("0001-01-01T00:00:00")
        assert _day(parse_date, "0001-01-01") - _day(parse_date, "-0001-12-31") == 1

    def test_1_bce_is_the_year_before_1_ce_for_every_type(self) -> None:
        # 1 BCE is a leap year.
        assert _day(parse_g_year, "0001") - _day(parse_g_year, "-0001") == 366
        assert _day(parse_g_year_month, "0001-01") - _day(parse_g_year_month, "-0001-12") == 31

    @pytest.mark.parametrize("value", ["-0001-02-29", "-0005-02-29", "-0401-02-29", "-12001-02-29"])
    def test_bce_leap_years_follow_the_gregorian_cycle(self, value: str) -> None:
        assert parse_date(value) is not None

    @pytest.mark.parametrize("value", ["-0002-02-29", "-0004-02-29", "-0101-02-29", "-0100-02-29"])
    def test_other_bce_years_have_no_leap_day(self, value: str) -> None:
        assert parse_date(value) is None

    def test_time_zone_normalisation_crosses_the_boundary(self) -> None:
        assert parse_date_time("-0001-12-31T23:00:00-02:00") == parse_date_time("0001-01-01T01:00:00Z")
        assert parse_date_time("0001-01-01T01:00:00+03:00") == parse_date_time("-0001-12-31T22:00:00Z")
        assert parse_date("0001-01-01+05:00") == parse_date_time("-0001-12-31T19:00:00Z")

    @pytest.mark.parametrize(
        ("parser", "value"),
        [
            (parse_date, "0000-12-31"),
            (parse_date_time, "0000-01-01T00:00:00"),
            (parse_g_year, "0000"),
            (parse_g_year_month, "0000-01"),
            (parse_date, "-0000-01-01"),
        ],
    )
    def test_lexical_year_zero_is_rejected(self, parser: Callable[[str], XsInstant | None], value: str) -> None:
        assert parser(value) is None


class TestParseGYear:
    def test_year_starts_at_january_first(self) -> None:
        assert parse_g_year("2024") == parse_date("2024-01-01")
        assert parse_g_year("2024Z") == parse_date_time("2024-01-01T00:00:00Z")

    def test_negative_years_keep_their_sign(self) -> None:
        negative = parse_g_year("-12024")
        positive = parse_g_year("12024")
        assert negative is not None and positive is not None
        assert negative.compare(positive) == -1

    @pytest.mark.parametrize("value", ["0000", "202", "+2024", "2024-01"])
    def test_rejects_invalid_lexical_values(self, value: str) -> None:
        assert parse_g_year(value) is None


class TestParseGYearMonth:
    def test_month_starts_at_first_day(self) -> None:
        assert parse_g_year_month("2024-02") == parse_date("2024-02-01")
        assert parse_g_year_month("-12024-12-14:00") is not None

    @pytest.mark.parametrize("value", ["2024", "2024-13", "2024-00", "2024-02-01"])
    def test_rejects_invalid_lexical_values(self, value: str) -> None:
        assert parse_g_year_month(value) is None


class TestCompare:
    def _instant(self, value: str) -> XsInstant:
        instant = parse_date_time(value)
        assert instant is not None
        return instant

    def test_orders_same_zoning(self) -> None:
        assert self._instant("-12024-01-01T00:00:00").compare(self._instant("2024-01-01T00:00:00")) == -1
        assert self._instant("12024-01-01T00:00:00").compare(self._instant("2024-01-01T00:00:00")) == 1
        assert self._instant("2024-01-01T00:00:00Z").compare(self._instant("2024-01-01T01:00:00+01:00")) == 0

    def test_mixed_zoning_is_indeterminate_within_fourteen_hours(self) -> None:
        assert self._instant("2024-01-01T00:00:00Z").compare(self._instant("2024-01-01T00:00:00")) is None
        assert self._instant("2024-01-01T00:00:00Z").compare(self._instant("2024-01-01T14:00:00")) is None
        assert self._instant("2024-01-01T00:00:00Z").compare(self._instant("2024-01-01T14:00:01")) == -1
        assert self._instant("2024-01-01T14:00:01").compare(self._instant("2024-01-01T00:00:00Z")) == 1


class TestParseTime:
    def test_seconds_into_the_day(self) -> None:
        assert parse_time("01:02:03.5") == Decimal("3723.5")

    @pytest.mark.parametrize(
        "first, second",
        [
            ("24:00:00", "00:00:00"),
            ("12:00:00Z", "13:00:00+01:00"),
            ("00:00:00+01:00", "23:00:00Z"),
            ("23:30:00-01:00", "00:30:00Z"),
            ("12:00:00.0", "12:00:00"),
        ],
    )
    def test_lexical_forms_of_one_time_are_equal(self, first: str, second: str) -> None:
        assert parse_time(first) == parse_time(second)

    @pytest.mark.parametrize("value", ["24:00:01", "12:60:00", "12:00", "T12:00:00", "12:00:00+15:00"])
    def test_rejects_invalid_lexical_values(self, value: str) -> None:
        assert parse_time(value) is None


class TestParseRecurring:
    def test_leap_day_exists(self) -> None:
        assert parse_g_month_day("--02-29") is not None

    def test_values_order_through_the_year(self) -> None:
        values = ["--01-01", "--02-29", "--12-31"]
        positions = [parse_g_month_day(value) for value in values]
        assert positions == sorted(positions)

    def test_time_zone_moves_the_value_into_the_previous_day(self) -> None:
        assert parse_g_month_day("--12-31+14:00") == parse_g_month_day("--12-30-10:00")

    @pytest.mark.parametrize(
        "parser, first, second",
        [
            (parse_g_month_day, "--12-25Z", "--12-25+00:00"),
            (parse_g_day, "---05Z", "---05+00:00"),
            (parse_g_month, "--06Z", "--06+00:00"),
        ],
    )
    def test_lexical_forms_of_one_value_are_equal(
        self, parser: Callable[[str], Decimal | None], first: str, second: str
    ) -> None:
        assert parser(first) == parser(second)

    @pytest.mark.parametrize(
        "parser, value",
        [
            (parse_g_month_day, "--02-30"),
            (parse_g_month_day, "--13-01"),
            (parse_g_day, "---32"),
            (parse_g_month, "--00"),
            (parse_g_month, "2024-06"),
        ],
    )
    def test_rejects_invalid_lexical_values(self, parser: Callable[[str], Decimal | None], value: str) -> None:
        assert parser(value) is None
