import re
from datetime import date

from arelle.plugin.validate.IRD.rules.nvad_identifiers import basisPeriodWindow

_YEAR = re.compile(r"^20(\d{2})/(\d{2})$")


def test_consecutive_assessment_year_window() -> None:
    assert basisPeriodWindow("2025/26", _YEAR) == (date(2025, 4, 1), date(2026, 3, 31))


def test_non_consecutive_and_malformed_years_have_no_window() -> None:
    assert basisPeriodWindow("2025/99", _YEAR) is None
    assert basisPeriodWindow("25/26", _YEAR) is None


def test_century_rollover_uses_the_following_calendar_year() -> None:
    assert basisPeriodWindow("2099/00", _YEAR) == (date(2099, 4, 1), date(2100, 3, 31))
