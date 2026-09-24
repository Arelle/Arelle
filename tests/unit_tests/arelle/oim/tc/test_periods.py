from __future__ import annotations

from decimal import Decimal

import pytest

from arelle.oim.tc import xs_dates
from arelle.oim.tc.periods import parse_period


class TestParsePeriod:
    @pytest.mark.parametrize(
        "value, expected_start, expected_end",
        [
            ("2024", (2024, 1, 1), (2025, 1, 1)),
            ("2024@start", (2024, 1, 1), (2024, 1, 1)),
            ("2024@end", (2025, 1, 1), (2025, 1, 1)),
            ("2024H2", (2024, 7, 1), (2025, 1, 1)),
            ("2024Q2", (2024, 4, 1), (2024, 7, 1)),
            ("2024Q4@end", (2025, 1, 1), (2025, 1, 1)),
            ("2024-02", (2024, 2, 1), (2024, 3, 1)),
            ("2024-12", (2024, 12, 1), (2025, 1, 1)),
            # 2024 starts on a Monday, 2021 starts on a Friday.
            ("2024W01", (2024, 1, 1), (2024, 1, 8)),
            ("2021W01", (2021, 1, 4), (2021, 1, 11)),
            ("2020W53", (2020, 12, 28), (2021, 1, 4)),
            ("2024-02-29", (2024, 2, 29), (2024, 3, 1)),
            ("2024-01-01..2024-12-31", (2024, 1, 1), (2025, 1, 1)),
            ("2024-01-01..2024-01-01", (2024, 1, 1), (2024, 1, 2)),
            ("2024-01-01T00:00:00/2024-07-01T00:00:00", (2024, 1, 1), (2024, 7, 1)),
            ("2024-01-01T00:00:00Z", (2024, 1, 1), (2024, 1, 1)),
            ("-0001", (0, 1, 1), (1, 1, 1)),
        ],
    )
    def test_period_bounds(
        self,
        value: str,
        expected_start: tuple[int, int, int],
        expected_end: tuple[int, int, int],
    ) -> None:
        bounds = parse_period(value)
        assert bounds is not None
        start, end = bounds
        assert (start.day, start.second) == (
            xs_dates.days_since_epoch(*expected_start),
            0,
        )
        assert (end.day, end.second) == (xs_dates.days_since_epoch(*expected_end), 0)

    def test_time_of_day_is_kept(self) -> None:
        bounds = parse_period("2024-01-01T12:30:00/2024-01-01T13:00:00")
        assert bounds is not None
        start, end = bounds
        assert (start.second, end.second) == (Decimal(45000), Decimal(46800))

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "x",
            "0000",
            "2024-13",
            "2024W53",
            "2024-02-30",
            "2024Q5",
            "2024-07-01T00:00:00/2024-01-01T00:00:00",
            "2024-12-31..2024-01-01",
            "2024-01-01T00:00:00/2024-01-01T00:00:00",
        ],
    )
    def test_invalid_periods_have_no_bounds(self, value: str) -> None:
        assert parse_period(value) is None
