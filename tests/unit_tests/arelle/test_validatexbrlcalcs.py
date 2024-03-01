from __future__ import annotations
import pytest
from _decimal import Decimal, InvalidOperation

from arelle.ValidateXbrlCalcs import insignificantDigits


@pytest.mark.parametrize('value, precision, decimals, scale, result, error', [
    # precision
    ('1234', '-1', None, None, ('0', '1234'), None),
    ('1234', '0', None, None, None, None),
    ('1234', '1', None, None, ('1000', '234'), None),
    ('1234', '2', None, None, ('1200', '34'), None),
    ('1234', '3', None, None, ('1230', '4'), None),
    ('1234', '4', None, None, None, None),
    ('1234', '5', None, None, None, None),

    ('1234.5678', '-2', None, None, ('0', '1234.5678'), None),
    ('1234.5678', '-1', None, None, ('0', '1234.5678'), None),
    ('1234.5678', '0', None, None, None, None),
    ('1234.5678', '1', None, None, ('1000', '234.5678'), None),
    ('1234.5678', '5', None, None, ('1234.5', '0.0678'), None),
    ('1234.5678', '9', None, None, None, None),

    # decimals
    ('1234', None, '-5', None, ('0', '1234'), None),
    ('1234', None, '-1', None, ('1230', '4'), None),
    ('1234', None, '0', None, None, None),
    ('1234', None, '1', None, None, None),

    ('1234.5678', None, '-5', None, ('0', '1234.5678'), None),
    ('1234.5678', None, '-1', None, ('1230', '4.5678'), None),
    ('1234.5678', None, '0', None, ('1234', '0.5678'), None),
    ('1234.5678', None, '1', None, ('1234.5', '0.0678'), None),
    ('1234.5678', None, '5', None, None, None),

    # precision + scale
    ('1234', '-1', None, '-1', None, None),
    ('1234', '-1', None, '0', ('0', '1234'), None),
    ('1234', '-1', None, '1', ('0', '12340'), None),
    ('1234', '0', None, '-1', None, None),
    ('1234', '0', None, '0', None, None),
    ('1234', '0', None, '1', None, None),
    ('1234', '1', None, '-5', None, None),
    ('1234', '1', None, '-1', None, None),
    ('1234', '1', None, '0', ('1000', '234'), None),
    ('1234', '1', None, '1', ('12000', '340'), None),

    ('1234.5678', '-1', None, '-1', ('123.45', '0.00678'), None),
    ('1234.5678', '-1', None, '0', ('0', '1234.5678'), None),
    ('1234.5678', '-1', None, '1', ('0', '12345.678'), None),
    ('1234.5678', '0', None, '-1', None, None),
    ('1234.5678', '0', None, '0', None, None),
    ('1234.5678', '0', None, '1', None, None),
    ('1234.5678', '1', None, '-1', ('123.4567', '0.00008'), None),
    ('1234.5678', '1', None, '0', ('1000', '234.5678'), None),
    ('1234.5678', '1', None, '1', ('12000', '345.678'), None),

    # decimals + scale
    ('1234', None, '-1', '-5', ('0', '0.01234'), None),
    ('1234', None, '-1', '-1', ('120', '3.4'), None),
    ('1234', None, '-1', '0', ('1230', '4'), None),
    ('1234', None, '-1', '1', None, None),
    ('1234', None, '-1', '2', None, None),
    ('1234', None, '0', '-5', ('0', '0.01234'), None),
    ('1234', None, '0', '-1', ('123', '0.4'), None),
    ('1234', None, '0', '0', None, None),
    ('1234', None, '0', '1', None, None),
    ('1234', None, '1', '-5', ('0', '0.01234'), None),
    ('1234', None, '1', '-1', None, None),
    ('1234', None, '1', '0', None, None),
    ('1234', None, '1', '1', None, None),

    ('1234.5678', None, '-1', '-5', ('0', '0.012345678'), None),
    ('1234.5678', None, '-1', '-1', ('120', '3.45678'), None),
    ('1234.5678', None, '-1', '0', ('1230', '4.5678'), None),
    ('1234.5678', None, '-1', '1', ('12340', '5.678'), None),
    ('1234.5678', None, '0', '-5', ('0', '0.012345678'), None),
    ('1234.5678', None, '0', '-1', ('123', '0.45678'), None),
    ('1234.5678', None, '0', '0', ('1234', '0.5678'), None),
    ('1234.5678', None, '0', '1', ('12345', '0.678'), None),
    ('1234.5678', None, '1', '-5', ('0', '0.012345678'), None),
    ('1234.5678', None, '1', '-1', ('123.4', '0.05678'), None),
    ('1234.5678', None, '1', '0', ('1234.5', '0.0678'), None),
    ('1234.5678', None, '1', '1', ('12345.6', '0.078'), None),

    # large precision
    ('1',  '1', None, None, None, None),
    ('1', '27', None, None, None, None),
    ('1', '28', None, None, None, None),
    ('1', '29', None, None, None, InvalidOperation),
    ('1', '30', None, None, None, None),

    ('1',  '1', None, '1', None, None),
    ('1', '27', None, '1', None, None),
    ('1', '28', None, '1', None, InvalidOperation),
    ('1', '29', None, '1', None, InvalidOperation),
    ('1', '30', None, '1', None, None),

    ('1',  '1', None, '2', None, None),
    ('1', '27', None, '2', None, InvalidOperation),
    ('1', '28', None, '2', None, InvalidOperation),
    ('1', '29', None, '2', None, InvalidOperation),
    ('1', '30', None, '2', None, None),

    # large decimals
    ('1', None, '27', None, None, None),
    ('1', None, '28', None, None, InvalidOperation),
    ('1', None, '29', None, None, None),

    ('1', None, '26', '1', None, None),
    ('1', None, '27', '1', None, InvalidOperation),
    ('1', None, '28', '1', None, InvalidOperation),
    ('1', None, '29', '1', None, None),

    ('1', None, '25', '2', None, None),
    ('1', None, '26', '2', None, InvalidOperation),
    ('1', None, '27', '2', None, InvalidOperation),
    ('1', None, '28', '2', None, InvalidOperation),
    ('1', None, '29', '2', None, None),

    # large whole values
    ('1E27', None,  '0', None, None, None),
    ('1E28', None,  '0', None, None, InvalidOperation),
    ('1E26', None,  '1', None, None, None),
    ('1E27', None,  '1', None, None, InvalidOperation),

    # large fractional values
    ('1.1E27', None,  '0', None, None, None),
    ('1.1E28', None,  '0', None, None, InvalidOperation),
    ('1.1E26', None,  '1', None, None, None),
    ('1.1E27', None,  '1', None, None, InvalidOperation),
    ('123456789012345678901234567.1', None,  '0', None, ('123456789012345678901234567', '0.1'), None),
    ('12345678901234567890123456789.1', None,  '0', None, None, InvalidOperation),

    # small fractional values
    ('1E-100', None,  '0', None, ('0', '1E-100'), None),
    ('1.1E-100', None,  '0', None, ('0', '1.1E-100'), None),
    ('0.1000000000000000000000000001', None,  '0', None, ('0', '0.1000000000000000000000000001'), None),
    ('0.10000000000000000000000000001', None,  '0', None, ('0', '0.1'), None),
    ('0.01000000000000000000000000001', None,  '0', '1', ('0', '0.1000000000000000000000000001'), None),
    ('0.010000000000000000000000000001', None,  '0', '1', ('0', '0.1'), None),
])
def test_insignificantDigits(
        value: str,
        precision: str | None,
        decimals: str | None,
        scale: str | None,
        result: tuple[str, str] | None,
        error: type | None) -> None:
    expected_result = (Decimal(result[0]), Decimal(result[1])) \
        if isinstance(result, tuple) \
        else result
    actual_error = None
    actual_result = None
    try:
        actual_result = insignificantDigits(
            Decimal(value) if value is not None else None,
            Decimal(precision) if precision is not None else None,
            Decimal(decimals) if decimals is not None else None,
            Decimal(scale) if scale is not None else None
        )
    except Exception as exc:
        actual_error = exc
    assert (actual_error is None and error is None) or type(actual_error) == error
    assert actual_result == expected_result
