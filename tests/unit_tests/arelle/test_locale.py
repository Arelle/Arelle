from __future__ import annotations
from typing import Any
import pytest
from decimal import Decimal
from arelle.Locale import format_decimal
from arelle.Locale import getUserLocale


d = Decimal('-1234567.8901')

@pytest.mark.parametrize(
    'params, result',
    [
        (
            {
                'conv': getUserLocale()[0],
                'value': d,
                'curr': '$',
                'neg': '-'
            },
            '-$1,234,567.89'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': d,
                'fractPlaces': 0,
                'sep': '.',
                'dp': '',
                'trailneg': '-'
            },
            '1.234.568-'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': d,
                'curr': '$',
                'neg': '(',
                'trailneg': ')'
            },
            '($1,234,567.89)'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': Decimal(123456789),
                'sep': ' '
            },
            '123 456 789.00'
        ),
        (
            {
                'conv': getUserLocale()[0],
                'value': Decimal('-0.02'),
                'neg': '<',
                'trailneg': '>'
            },
            '<0.02>'
        ),
    ]
)
def test_format_decimal(params: dict[str, Any], result: str) -> None:
    assert format_decimal(**params) == result
