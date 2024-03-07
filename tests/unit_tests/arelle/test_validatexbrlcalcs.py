from __future__ import annotations
import pytest
from _decimal import Decimal, InvalidOperation

from arelle.ValidateXbrlCalcs import insignificantDigits


@pytest.mark.parametrize('value, decimals, result', [
    # decimals
    ('1234', '-5', ('0', '1234')),
    ('1234', '-1', ('1230', '4')),
    ('1234', '0', None),
    ('1234', '1', None),
    ('-1234', '-5', ('0', '1234')),
    ('-1234', '-1', ('-1230', '4')),
    ('-1234', '0', None),
    ('-1234', '1', None),

    ('1234.5678', '-5', ('0', '1234.5678')),
    ('1234.5678', '-1', ('1230', '4.5678')),
    ('1234.5678', '0', ('1234', '0.5678')),
    ('1234.5678', '1', ('1234.5', '0.0678')),
    ('1234.5678', '5', None),

    ('-1234.5678', '-5', ('0', '1234.5678')),
    ('-1234.5678', '-1', ('-1230', '4.5678')),
    ('-1234.5678', '0', ('-1234', '0.5678')),
    ('-1234.5678', '1', ('-1234.5', '0.0678')),
    ('-1234.5678', '5', None),

    # large decimals
    ('1', '27', None),
    ('1', '28', None),
    ('1', '29', None),

    ('1', '26', None),
    ('1', '27', None),
    ('1', '28', None),
    ('1', '29', None),

    ('1', '25', None),
    ('1', '26', None),
    ('1', '27', None),
    ('1', '28', None),
    ('1', '29', None),

    ('1.1E26', '-26', ('1E26', '1E25')),
    ('1.1E27', '-27', ('1E27', '1E26')),
    ('1.1E28', '-28', None),  # 28 decimals too many for quantization
    ('1.1E-27', '27', ('1E-27', '1E-28')),
    ('1.1E-28', '28', ('1E-28', '1E-29')),
    ('1.1E-29', '29', ('1E-29', '1E-30')),

    ('-1.1E26', '-26', ('-1E26', '1E25')),
    ('-1.1E27', '-27', ('-1E27', '1E26')),
    ('-1.1E28', '-28', None),  # 28 decimals too many for quantization
    ('-1.1E-27', '27', ('-1E-27', '1E-28')),
    ('-1.1E-28', '28', ('-1E-28', '1E-29')),
    ('-1.1E-29', '29', ('-1E-29', '1E-30')),

    # large whole values
    ('1E27',  '0', None),
    ('1E28',  '0', None),
    ('1E26',  '1', None),
    ('1E27',  '1', None),

    # large fractional values
    ('1.1E27', '0', None),
    ('1.1E28', '0', None),
    ('1.1E26', '1', None),
    ('1.1E27', '1', None),
    ('123456789012345678901234567.1', '0', ('123456789012345678901234567', '0.1')),
    ('12345678901234567890123456789.1', '0', None),

    # small fractional values
    ('1E-100', '0', ('0', '1E-100')),
    ('1.1E-100', '0', ('0', '1.1E-100')),
    ('0.1000000000000000000000000001', '0', ('0', '0.1000000000000000000000000001')),
    ('0.10000000000000000000000000001', '0', ('0', '0.1')),
])
def test_insignificantDigits(
        value: str,
        decimals: str,
        result: tuple[str, str] | None) -> None:
    expected_result = (Decimal(result[0]), Decimal(result[1])) \
        if isinstance(result, tuple) \
        else result
    actual_result = insignificantDigits(
        Decimal(value),
        Decimal(decimals)
    )
    assert actual_result == expected_result
