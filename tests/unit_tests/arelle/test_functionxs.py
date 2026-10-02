"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from arelle import FunctionXs, ModelValue
from arelle.formula import XPathContext
from arelle.formula.XPathParser import ProgHeader

GREGORIAN_CASES = [
    ("gYearMonth", "2024-06", ("year", "month"), (2024, 6)),
    ("gYear", "2024", ("year",), (2024,)),
    ("gMonthDay", "--02-29", ("month", "day"), (2, 29)),
    ("gDay", "---31", ("day",), (31,)),
    ("gMonth", "--12", ("month",), (12,)),
]

TIMEZONE_CASES = [
    ("", None, ""),
    ("Z", 0, "Z"),
    ("+00:00", 0, "Z"),
    ("-00:00", 0, "Z"),
    ("+05:30", 330, "+05:30"),
    ("-05:30", -330, "-05:30"),
    ("+00:30", 30, "+00:30"),
    ("-00:30", -30, "-00:30"),
    ("+14:00", 840, "+14:00"),
    ("-14:00", -840, "-14:00"),
]


@pytest.fixture
def xpathContext() -> Mock:
    context = Mock(spec=XPathContext.XPathContext)
    context.atomize.side_effect = lambda _p, item: item
    return context


@pytest.mark.parametrize("localname,lexical,fieldNames,expectedFields", GREGORIAN_CASES)
@pytest.mark.parametrize("suffix,offsetMinutes,expectedSuffix", TIMEZONE_CASES)
def test_g_type_timezone(
    xpathContext: Mock,
    localname: str,
    lexical: str,
    fieldNames: tuple[str, ...],
    expectedFields: tuple[int, ...],
    suffix: str,
    offsetMinutes: int | None,
    expectedSuffix: str,
) -> None:
    header = Mock(spec=ProgHeader, sourceStr="")
    result = FunctionXs.call(xpathContext, header, localname, [[lexical + suffix]])
    assert type(result) is getattr(ModelValue, localname)
    assert tuple(getattr(result, field) for field in fieldNames) == expectedFields
    if offsetMinutes is None:
        assert result.tzinfo is None
    else:
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == timedelta(minutes=offsetMinutes)
    expectedText = lexical + expectedSuffix
    assert str(result) == expectedText
    assert repr(result) == expectedText
    assert FunctionXs.call(xpathContext, header, "string", [[result]]) == expectedText


@pytest.mark.parametrize("localname,lexical", [(case[0], case[1]) for case in GREGORIAN_CASES])
@pytest.mark.parametrize("suffix", ["+14:01", "-14:01", "+05:60", "+0530"])
def test_g_type_invalid_timezone(
    xpathContext: Mock, localname: str, lexical: str, suffix: str,
) -> None:
    with pytest.raises(XPathContext.XPathException) as exc:
        FunctionXs.call(xpathContext, Mock(spec=ProgHeader, sourceStr=""), localname, [[lexical + suffix]])
    assert exc.value.code == "err:FORG0001"


@pytest.mark.parametrize("localname,lexical", [
    ("gYearMonth", "2024-13Z"),
    ("gYear", "202Z"),
    ("gMonthDay", "--02-30Z"),
    ("gMonthDay", "--04-31+05:30"),
    ("gDay", "---32Z"),
    ("gMonth", "--13Z"),
    ("gYear", ""),
    ("gYear", 2024),
])
def test_g_type_invalid_value(xpathContext: Mock, localname: str, lexical: Any) -> None:
    with pytest.raises(XPathContext.XPathException) as exc:
        FunctionXs.call(xpathContext, Mock(spec=ProgHeader, sourceStr=""), localname, [[lexical]])
    assert exc.value.code == "err:FORG0001"


@pytest.mark.parametrize("localname,lexical", [("gYear", "10000Z"), ("gYearMonth", "10000-06Z")])
def test_g_type_large_year(xpathContext: Mock, localname: str, lexical: str) -> None:
    result = FunctionXs.call(xpathContext, Mock(spec=ProgHeader, sourceStr=""), localname, [[lexical]])
    assert result.year == 10000
    assert result.tzinfo.utcoffset(None) == timedelta(0)
    assert str(result) == lexical


@pytest.mark.parametrize("localname,left,right", [
    ("gDay", "---14-10:00", "---15+14:00"),
    ("gMonthDay", "--06-14-10:00", "--06-15+14:00"),
])
def test_g_type_equal_instants(xpathContext: Mock, localname: str, left: str, right: str) -> None:
    header = Mock(spec=ProgHeader, sourceStr="")
    leftValue = FunctionXs.call(xpathContext, header, localname, [[left]])
    rightValue = FunctionXs.call(xpathContext, header, localname, [[right]])
    assert leftValue == rightValue
    assert hash(leftValue) == hash(rightValue)


def test_g_type_empty_sequence(xpathContext: Mock) -> None:
    assert FunctionXs.call(xpathContext, Mock(spec=ProgHeader, sourceStr=""), "gYear", [()]) == ()


def test_g_type_multiple_values(xpathContext: Mock) -> None:
    with pytest.raises(XPathContext.FunctionArgType) as exc:
        FunctionXs.call(xpathContext, Mock(spec=ProgHeader, sourceStr=""), "gYear", [["2024", "2025"]])
    assert exc.value.errCode == "err:XPTY0004"
