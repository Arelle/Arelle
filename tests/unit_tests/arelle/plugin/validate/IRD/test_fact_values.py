from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from arelle.plugin.validate.IRD.rules import getDateValue, getNumericValue


def test_numeric_values_keep_exact_decimals() -> None:
    assert getNumericValue(SimpleNamespace(xValue=Decimal("1.10"))) == Decimal("1.10")
    assert getNumericValue(SimpleNamespace(xValue=5)) == Decimal(5)
    assert getNumericValue(SimpleNamespace(xValue=0.1)) == Decimal("0.1")


def test_booleans_and_strings_are_not_amounts() -> None:
    assert getNumericValue(SimpleNamespace(xValue=False)) is None
    assert getNumericValue(SimpleNamespace(xValue=True)) is None
    assert getNumericValue(SimpleNamespace(xValue="1")) is None


def test_date_values_cover_datetimes_and_dates() -> None:
    assert getDateValue(SimpleNamespace(xValue=datetime(2025, 4, 1, 12, 0))) == date(2025, 4, 1)
    assert getDateValue(SimpleNamespace(xValue=date(2026, 3, 31))) == date(2026, 3, 31)
    assert getDateValue(SimpleNamespace(xValue="2025-04-01")) is None
