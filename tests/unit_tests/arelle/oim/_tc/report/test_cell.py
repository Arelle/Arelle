from __future__ import annotations

import pytest

from arelle.oim._tc.report.cell import (
    UnknownSpecialValue,
    effective_value,
    row_has_value,
)


class TestEffectiveValue:
    @pytest.mark.parametrize(
        "literal, expected",
        [
            (None, None),
            ("", None),
            ("#nil", None),
            ("#none", None),
            ("#empty", ""),
            ("##empty", "#empty"),
            ("###", "##"),
            ("abc", "abc"),
            (" ", " "),
            ("a#b", "a#b"),
        ],
    )
    def test_special_value_processing(
        self, literal: str | None, expected: str | None
    ) -> None:
        assert effective_value(literal) == expected

    @pytest.mark.parametrize("literal", ["#", "#foo", "#Nil", "#empty "])
    def test_unknown_special_values_are_rejected(self, literal: str) -> None:
        with pytest.raises(UnknownSpecialValue):
            effective_value(literal)


class TestRowHasValue:
    @pytest.mark.parametrize(
        "row, expected",
        [
            ([], False),
            ([""], False),
            (["", "", ""], False),
            ([" ", "", ""], True),
            (["", "#none"], True),
            (["", "x"], True),
        ],
    )
    def test_row_has_value(self, row: list[str], expected: bool) -> None:
        assert row_has_value(row) is expected
