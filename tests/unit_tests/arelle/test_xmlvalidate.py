from __future__ import annotations

import datetime
from _decimal import Decimal
from fractions import Fraction
from math import inf, isnan, nan
from typing import Any
from unittest import TestCase
from unittest.mock import Mock

import pytest
import regex

from arelle.ModelDtsObject import _EnumerationFacet
from arelle.ModelValue import DateTime, QName, Time, gDay, gMonth, gMonthDay, gYear, gYearMonth, isoDuration
from arelle.XmlValidate import (
    NCNamePattern,
    NMTOKENPattern,
    XsdPattern,
    namePattern,
    validateFacetValueString,
    validateValue,
    validateValueString,
)
from arelle.XmlValidateConst import INVALID, UNKNOWN, VALID, VALID_ID, VALID_NO_CONTENT

FLOAT_CASES = [
    {"value": "-1", "expected": (-1, -1, VALID)},
    {"value": "-1.1", "expected": (-1.1, -1.1, VALID)},
    {"value": "-10", "expected": (-10, -10, VALID)},
    {"value": "-10.1", "expected": (-10.1, -10.1, VALID)},
    {"value": "0", "expected": (0, 0, VALID)},
    {"value": "0.0", "expected": (0, 0, VALID)},
    {"value": "1", "expected": (1, 1, VALID)},
    {"value": "1.1", "expected": (1.1, 1.1, VALID)},
    {"value": "10", "expected": (10, 10, VALID)},
    {"value": "10.1", "expected": (10.1, 10.1, VALID)},
    {"value": ".1", "expected": (0.1, 0.1, VALID)},
    {"value": "1.", "expected": (1, 1, VALID)},
    {"value": "1e0", "expected": (1, 1, VALID)},
    {"value": "1e1", "expected": (10, 10, VALID)},
    {"value": "1E-1", "expected": (0.1, 0.1, VALID)},
    {"value": "1.1e0", "expected": (1.1, 1.1, VALID)},
    {"value": "1.1e1", "expected": (11, 11, VALID)},
    {"value": "1.1E-1", "expected": (0.11, 0.11, VALID)},
    {"value": "INF", "expected": (inf, inf, VALID)},
    {"value": "NaN", "expected": (nan, nan, VALID)},
    {"value": "1.1.1", "expected": ("=", None, INVALID)},
    {"value": "inf", "expected": ("=", None, INVALID)},
    {"value": "nan", "expected": ("=", None, INVALID)},
    {"value": "1e", "expected": ("=", None, INVALID)},
    {"value": "1E", "expected": ("=", None, INVALID)},
    {"value": "1.0e", "expected": ("=", None, INVALID)},
    {"value": "1.0E", "expected": ("=", None, INVALID)},
]

NON_ZERO_DECIMAL_CASES = [
    {"value": "-1", "expected": (-1, Decimal(-1), VALID)},
    {"value": "-1.1", "expected": (-1.1, Decimal("-1.1"), VALID)},
    {"value": "-10", "expected": (-10, Decimal(-10), VALID)},
    {"value": "-10.1", "expected": (-10.1, Decimal("-10.1"), VALID)},
    {"value": "1", "expected": (1, Decimal(1), VALID)},
    {"value": "1.1", "expected": (1.1, Decimal("1.1"), VALID)},
    {"value": "10", "expected": (10, Decimal(10), VALID)},
    {"value": "10.1", "expected": (10.1, Decimal("10.1"), VALID)},
    {"value": ".1", "expected": (0.1, Decimal("0.1"), VALID)},
    {"value": "1.", "expected": (1, Decimal(1), VALID)},
    {"value": "1.1.1", "expected": ("=", None, INVALID)},
]

BASE_XSD_TYPES = {
    None: [
        {"value": "*", "expected": (None, None, UNKNOWN)},
    ],
    "_other": [
        {"value": "*", "expected": ("=", "=", VALID)},
    ],
    "anyURI": [
        {"value": "http://test.test/test", "expected": ("=", "=", VALID)},
        {"value": "ftp://test.test/test", "expected": ("=", "=", VALID)},
        {"value": "/test.test/test", "expected": ("=", "=", VALID)},
        {"value": "test.test/test", "expected": ("=", "=", VALID)},
        {"value": "\\escaped", "expected": ("=", "%5Cescaped", VALID)},
        {"value": "http://example.com/%20valid", "expected": ("=", "=", VALID)},
        {"value": "http://example.com/path#section", "expected": ("=", "=", VALID)},
        {"value": ":invalid:", "expected": ("=", None, INVALID)},
        {"value": "http://example.com/%ZZ", "expected": ("=", None, INVALID)},
        {"value": "http://example.com/path#frag1#frag2", "expected": ("=", None, INVALID)},
    ],
    "boolean": [
        {"value": "true", "expected": (True, True, VALID)},
        {"value": "True", "expected": ("=", None, INVALID)},
        {"value": "TRUE", "expected": ("=", None, INVALID)},
        {"value": "1", "expected": (True, True, VALID)},
        {"value": "false", "expected": (False, False, VALID)},
        {"value": "False", "expected": ("=", None, INVALID)},
        {"value": "FALSE", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (False, False, VALID)},
    ],
    "byte": [
        {"value": "-129", "expected": ("=", None, INVALID)},
        {"value": "-128", "expected": (-128, -128, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "127", "expected": (127, 127, VALID)},
        {"value": "128", "expected": ("=", None, INVALID)},
    ],
    "date": [
        {"value": "2025-01-02", "expected": ("=", DateTime(2025, 1, 2), VALID)},
        {"value": "2025-01-02Z", "expected": ("=", DateTime(2025, 1, 2, tzinfo=datetime.timezone.utc), VALID)},
        {"value": "2025-01-02+01:30", "expected": ("=", DateTime(2025, 1, 2, tzinfo=datetime.timezone(datetime.timedelta(seconds=5400))), VALID)},
        {"value": "2025-01-02T03:04:05", "expected": ("=", None, INVALID)},
        {"value": "2025-01-02 T03:04:05", "expected": ("=", None, INVALID)},
        {"value": "2025-01-02T03:04:05+1:30", "expected": ("=", None, INVALID)},
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "01/02/2025", "expected": ("=", None, INVALID)},
        {"value": "0000-01-02", "expected": ("=", None, INVALID)},
    ],
    "dateTime": [
        {"value": "2025-01-02T03:04:05", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5), VALID)},
        {"value": "2025-01-02T03:04:05.6", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000), VALID)},
        {"value": "2025-01-02T03:04:05.6Z", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000, tzinfo=datetime.timezone.utc), VALID)},
        {"value": "2025-01-02T03:04:05.6+01:30", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000, tzinfo=datetime.timezone(datetime.timedelta(seconds=5400))), VALID)},
        {"value": "2025-01-02T03:04:05.6-01:30", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000, tzinfo=datetime.timezone(datetime.timedelta(seconds=-5400))), VALID)},
        {"value": "2025-01-02", "expected": ("=", None, INVALID)},
        {"value": "2025-01-02 T03:04:05", "expected": ("=", None, INVALID)},
        {"value": "2025-01-02T03:04:05+1:30", "expected": ("=", None, INVALID)},
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "01/02/2025", "expected": ("=", None, INVALID)},
        {"value": "0000-01-02T03:04:05", "expected": ("=", None, INVALID)},
    ],
    "decimal": NON_ZERO_DECIMAL_CASES + [
        {"value": "0", "expected": (0, Decimal(0), VALID)},
        {"value": "0.0", "expected": (0, Decimal(0), VALID)},
    ],
    "double": FLOAT_CASES,
    "duration": [
        {"value": "P1Y1M1D", "expected": ("=", isoDuration("P1Y1M1D"), VALID)},
        {"value": "P1Y1M1DT1H1M1S", "expected": ("=", isoDuration("P1Y1M1DT1H1M1S"), VALID)},
        {"value": "PT1H1M1S", "expected": ("=", isoDuration("PT1H1M1S"), VALID)},
        {"value": "1Y1M1D", "expected": ("=", None, INVALID)},
        {"value": "P1Y1M1D1H1M1S", "expected": ("=", None, INVALID)},
        {"value": "T1H1M1S", "expected": ("=", None, INVALID)},
    ],
    "ENTITIES": [
        {"value": "*invalid valid", "expected": ("=", "=", VALID)},  # TODO: this should fail but doesn't because it checks for `baseXsdTypePatterns` with key `ENTITIE`
        {"value": "valid valid", "expected": ("=", "=", VALID)},
    ],
    "ENTITY": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "valid", "expected": ("=", "=", VALID)},
    ],
    "enumerationHrefs": [
        {"value": "localName", "expected": ("localName", [QName(None, None, "localName")], VALID)},
        {"value": "#localName", "expected": ("#localName", [QName(None, None, "localName")], VALID)},
        {"value": "namespaceURI#localName", "expected": ("namespaceURI#localName", [QName(None, "namespaceURI", "localName")], VALID)},
        {"value": "localName1 localName2", "expected": ("localName1 localName2", [QName(None, None, "localName1"), QName(None, None, "localName2")], VALID)},
    ],
    "enumerationQNames": [
        {"value": "prefix:localName valid", "expected": ("=", [QName("prefix", "namespaceURI", "localName"), QName(None, None, "valid")], VALID)},
        {"value": "prefix:localName", "expected": ("=", [QName("prefix", "namespaceURI", "localName")], VALID)},
        {"value": "prefix:localName prefix:localName", "expected": ("=", [QName("prefix", "namespaceURI", "localName"), QName("prefix", "namespaceURI", "localName")], VALID)},
    ],
    "float": FLOAT_CASES,
    "fraction": [
        {"value": "0/1", "expected": ("=", Fraction(0, 1), VALID)},
        {"value": "1/1", "expected": ("=", Fraction(1, 1), VALID)},
        {"value": "2/1", "expected": ("=", Fraction(2, 1), VALID)},
        {"value": "1/1.1", "expected": ("=", Fraction(1/1.1), VALID)},
        {"value": "1.1/1", "expected": ("=", Fraction(1.1/1), VALID)},
        # {"value": "1/0", "expected": ("=", None, INVALID)},  # TODO: ArithmitecError should be caught
        {"value": "1/", "expected": ("=", None, INVALID)},
        {"value": "/1", "expected": ("=", None, INVALID)},
        {"value": "1.1", "expected": ("=", None, INVALID)},
    ],
    "gDay": [
        {"value": "---01", "expected": ("=", gDay(1), VALID)},
        {"value": "---31", "expected": ("=", gDay(31), VALID)},
        {"value": "---01Z", "expected": ("=", gDay(1), VALID)},
        {"value": "---01+01:11", "expected": ("=", gDay(1), VALID)},
        {"value": "---01-01:11", "expected": ("=", gDay(1), VALID)},
        {"value": "---01-14:00", "expected": ("=", gDay(1), VALID)},
        {"value": "01", "expected": ("=", None, INVALID)},
        {"value": "--01", "expected": ("=", None, INVALID)},
        {"value": "---1", "expected": ("=", None, INVALID)},
        {"value": "---00", "expected": ("=", None, INVALID)},
        {"value": "---32", "expected": ("=", None, INVALID)},
        {"value": "---111", "expected": ("=", None, INVALID)},
        {"value": "---0101:11", "expected": ("=", None, INVALID)},
        {"value": "---01Z1:11", "expected": ("=", None, INVALID)},
        {"value": "---01+01:60", "expected": ("=", None, INVALID)},
        {"value": "---01+15:00", "expected": ("=", None, INVALID)},
    ],
    "gMonth": [
        {"value": "--01", "expected": ("=", gMonth(1), VALID)},
        {"value": "--12", "expected": ("=", gMonth(12), VALID)},
        {"value": "--01Z", "expected": ("=", gMonth(1), VALID)},
        {"value": "--01+01:11", "expected": ("=", gMonth(1), VALID)},
        {"value": "--01-01:11", "expected": ("=", gMonth(1), VALID)},
        {"value": "--01-14:00", "expected": ("=", gMonth(1), VALID)},
        {"value": "01", "expected": ("=", None, INVALID)},
        {"value": "-01", "expected": ("=", None, INVALID)},
        {"value": "---01", "expected": ("=", None, INVALID)},
        {"value": "--1", "expected": ("=", None, INVALID)},
        {"value": "--00", "expected": ("=", None, INVALID)},
        {"value": "--13", "expected": ("=", None, INVALID)},
        {"value": "--111", "expected": ("=", None, INVALID)},
        {"value": "--0101:11", "expected": ("=", None, INVALID)},
        {"value": "--01Z1:11", "expected": ("=", None, INVALID)},
        {"value": "--01+01:60", "expected": ("=", None, INVALID)},
        {"value": "--01+15:00", "expected": ("=", None, INVALID)},
    ],
    "gMonthDay": [
        {"value": "--01-01", "expected": ("=", gMonthDay(1, 1), VALID)},
        {"value": "--01-31", "expected": ("=", gMonthDay(1, 31), VALID)},
        {"value": "--12-01", "expected": ("=", gMonthDay(12, 1), VALID)},
        {"value": "--01-01Z", "expected": ("=", gMonthDay(1, 1), VALID)},
        {"value": "--01-01+01:11", "expected": ("=", gMonthDay(1, 1), VALID)},
        {"value": "--01-01-01:11", "expected": ("=", gMonthDay(1, 1), VALID)},
        {"value": "--01-01-14:00", "expected": ("=", gMonthDay(1, 1), VALID)},
        {"value": "01-01", "expected": ("=", None, INVALID)},
        {"value": "-01-01", "expected": ("=", None, INVALID)},
        {"value": "---01-01", "expected": ("=", None, INVALID)},
        {"value": "--1-01", "expected": ("=", None, INVALID)},
        {"value": "--01-1", "expected": ("=", None, INVALID)},
        {"value": "--00-01", "expected": ("=", None, INVALID)},
        {"value": "--01-00", "expected": ("=", None, INVALID)},
        {"value": "--13-01", "expected": ("=", None, INVALID)},
        {"value": "--01-32", "expected": ("=", None, INVALID)},
        {"value": "--01-111", "expected": ("=", None, INVALID)},
        {"value": "--111-01", "expected": ("=", None, INVALID)},
        {"value": "--01-0101:11", "expected": ("=", None, INVALID)},
        {"value": "--01-01Z1:11", "expected": ("=", None, INVALID)},
        {"value": "--01-01+01:60", "expected": ("=", None, INVALID)},
        {"value": "--01-01+15:00", "expected": ("=", None, INVALID)},
    ],
    "gYear": [
        {"value": "-1000", "expected": ("=", gYear(1000), VALID)},
        {"value": "-10000", "expected": ("=", gYear(10000), VALID)},
        {"value": "-0001", "expected": ("=", gYear(1), VALID)},
        {"value": "0001", "expected": ("=", gYear(1), VALID)},
        {"value": "-0001Z", "expected": ("=", gYear(1), VALID)},
        {"value": "-0001+01:11", "expected": ("=", gYear(1), VALID)},
        {"value": "-0001-01:11", "expected": ("=", gYear(1), VALID)},
        {"value": "-0001-14:00", "expected": ("=", gYear(1), VALID)},
        {"value": "0000", "expected": ("=", None, INVALID)},
        {"value": "-0000", "expected": ("=", None, INVALID)},
        {"value": "0000Z", "expected": ("=", None, INVALID)},
        {"value": "--0001", "expected": ("=", None, INVALID)},
        {"value": "-01", "expected": ("=", None, INVALID)},
        {"value": "-00001", "expected": ("=", None, INVALID)},
        {"value": "-000101:11", "expected": ("=", None, INVALID)},
        {"value": "-0001Z1:11", "expected": ("=", None, INVALID)},
        {"value": "-0001+01:60", "expected": ("=", None, INVALID)},
        {"value": "-0001+15:00", "expected": ("=", None, INVALID)},
    ],
    "gYearMonth": [
        {"value": "-1000-01", "expected": ("=", gYearMonth(1000, 1), VALID)},
        {"value": "-10000-01", "expected": ("=", gYearMonth(10000, 1), VALID)},
        {"value": "-0001-01", "expected": ("=", gYearMonth(1, 1), VALID)},
        {"value": "0001-01", "expected": ("=", gYearMonth(1, 1), VALID)},
        {"value": "-0001-01Z", "expected": ("=", gYearMonth(1, 1), VALID)},
        {"value": "-0001-01+01:11", "expected": ("=", gYearMonth(1, 1), VALID)},
        {"value": "-0001-01-01:11", "expected": ("=", gYearMonth(1, 1), VALID)},
        {"value": "-0001-01-14:00", "expected": ("=", gYearMonth(1, 1), VALID)},
        {"value": "0000-01", "expected": ("=", None, INVALID)},
        {"value": "-0000-01", "expected": ("=", None, INVALID)},
        {"value": "0000-06Z", "expected": ("=", None, INVALID)},
        {"value": "--0001-01", "expected": ("=", None, INVALID)},
        {"value": "-01-01", "expected": ("=", None, INVALID)},
        {"value": "-00001-01", "expected": ("=", None, INVALID)},
        {"value": "-1000-13", "expected": ("=", None, INVALID)},
        {"value": "-0001-0101:11", "expected": ("=", None, INVALID)},
        {"value": "-0001-01Z1:11", "expected": ("=", None, INVALID)},
        {"value": "-0001-01+01:60", "expected": ("=", None, INVALID)},
        {"value": "-0001-01+15:00", "expected": ("=", None, INVALID)},
    ],
    "ID": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "valid", "expected": ("=", "=", VALID_ID)},
    ],
    "IDREF": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "valid", "expected": ("=", "=", VALID)},
    ],
    "IDREFS": [
        {"value": "*invalid valid", "expected": ("=", None, INVALID)},
        {"value": "valid valid", "expected": ("=", "=", VALID)},
    ],
    "int": [
        {"value": "-2147483649", "expected": ("=", None, INVALID)},
        {"value": "-2147483648", "expected": (-2147483648, -2147483648, VALID)},
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "2147483647", "expected": (2147483647, 2147483647, VALID)},
        {"value": "2147483648", "expected": ("=", None, INVALID)},
    ],
    "integer": [
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
    ],
    "language": [
        {"value": "valid", "expected": ("=", "=", VALID)},
        {"value": "*invalid", "expected": ("=", None, INVALID)},
    ],
    "languageOrEmpty": [
        {"value": "valid", "expected": ("=", "=", VALID)},
        {"value": "", "expected": ("=", "=", VALID)},
        {"value": "*invalid", "expected": ("=", None, INVALID)},
    ],
    "long": [
        {"value": "-9223372036854775809", "expected": ("=", None, INVALID)},
        {"value": "-9223372036854775808", "expected": (-9223372036854775808, -9223372036854775808, VALID)},
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "9223372036854775807", "expected": (9223372036854775807, 9223372036854775807, VALID)},
        {"value": "9223372036854775808", "expected": ("=", None, INVALID)},
    ],
    "Name": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "valid", "expected": ("=", "=", VALID)},
        {"value": ":valid", "expected": ("=", "=", VALID)},
    ],
    "NCName": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": ":invalid", "expected": ("=", None, INVALID)},
        {"value": "valid", "expected": ("=", "=", VALID)},
    ],
    "negativeInteger": [
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": ("=", None, INVALID)},
        {"value": "1", "expected": ("=", None, INVALID)},
    ],
    "NMTOKEN": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "valid", "expected": ("=", "=", VALID)},
    ],
    "NMTOKENS": [
        {"value": "*invalid valid", "expected": ("=", None, INVALID)},
        {"value": "valid valid", "expected": ("=", "=", VALID)},
    ],
    "noContent": [
        {"value": "", "expected": (None, None, VALID_NO_CONTENT)},
        {"value": " \t\n\r", "expected": (None, None, VALID_NO_CONTENT)},
        {"value": "invalid", "expected": ("=", None, INVALID)},
    ],
    "nonNegativeInteger": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
    ],
    "nonPositiveInteger": [
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": ("=", None, INVALID)},
    ],
    "normalizedString": [
        {"value": "*", "expected": ("=", "=", VALID)},
    ],
    "positiveInteger": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": ("=", None, INVALID)},
        {"value": "1", "expected": (1, 1, VALID)},
    ],
    "QName": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "prefix:localName", "expected": ("=", QName("prefix", "namespaceURI", "localName"), VALID)},
    ],
    "short": [
        {"value": "-32769", "expected": ("=", None, INVALID)},
        {"value": "-32768", "expected": (-32768, -32768, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "32767", "expected": (32767, 32767, VALID)},
        {"value": "32768", "expected": ("=", None, INVALID)},
    ],
    "string": [
        {"value": "*", "expected": ("=", "=", VALID)},
    ],
    "time": [
        {"value": "03:04:05", "expected": ("=", Time(3, 4, 5), VALID)},
        {"value": "03:04:05.6", "expected": ("=", Time(3, 4, 5, 600000), VALID)},
        {"value": "03:04:05.6Z", "expected": ("=", Time(3, 4, 5, 600000, tzinfo=datetime.timezone.utc), VALID)},
        {"value": "03:04:05.6+01:30", "expected": ("=", Time(3, 4, 5, 600000, tzinfo=datetime.timezone(datetime.timedelta(seconds=5400))), VALID)},
        {"value": "03:04:05.6-01:30", "expected": ("=", Time(3, 4, 5, 600000, tzinfo=datetime.timezone(datetime.timedelta(seconds=-5400))), VALID)},
        {"value": "3:04:05", "expected": ("=", None, INVALID)},
        {"value": "03:4:05", "expected": ("=", None, INVALID)},
        {"value": "03:04:5", "expected": ("=", None, INVALID)},
        {"value": "2025-01-02", "expected": ("=", None, INVALID)},
        {"value": "T03:04:05", "expected": ("=", None, INVALID)},
        {"value": "03:04:05+1:30", "expected": ("=", None, INVALID)},
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "01/02/2025", "expected": ("=", None, INVALID)},
    ],
    "token": [
        {"value": "*", "expected": ("=", "=", VALID)},
    ],
    "unsignedByte": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "255", "expected": (255, 255, VALID)},
        {"value": "256", "expected": ("=", None, INVALID)},
    ],
    "unsignedInt": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "4294967295", "expected": (4294967295, 4294967295, VALID)},
        {"value": "4294967296", "expected": ("=", None, INVALID)},
    ],
    "unsignedLong": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "18446744073709551615", "expected": (18446744073709551615, 18446744073709551615, VALID)},
        {"value": "18446744073709551616", "expected": ("=", None, INVALID)},
    ],
    "unsignedShort": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "65535", "expected": (65535, 65535, VALID)},
        {"value": "65536", "expected": ("=", None, INVALID)},
    ],
    "XBRLI_DATEUNION": [
        {"value": "2025-01-02", "expected": ("=", DateTime(2025, 1, 2), VALID)},
        {"value": "2025-01-02T03:04:05", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5), VALID)},
        {"value": "2025-01-02T03:04:05.6", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000), VALID)},
        {"value": "2025-01-02T03:04:05.6Z", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000, tzinfo=datetime.timezone.utc), VALID)},
        {"value": "2025-01-02T03:04:05.6+01:30", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000, tzinfo=datetime.timezone(datetime.timedelta(seconds=5400))), VALID)},
        {"value": "2025-01-02T03:04:05.6-01:30", "expected": ("=", DateTime(2025, 1, 2, 3, 4, 5, 600000, tzinfo=datetime.timezone(datetime.timedelta(seconds=-5400))), VALID)},
        {"value": "2025-01-02 T03:04:05", "expected": ("=", None, INVALID)},
        {"value": "2025-01-02T03:04:05+1:30", "expected": ("=", None, INVALID)},
        {"value": "*invalid", "expected": ("=", None, INVALID)},
        {"value": "01/02/2025", "expected": ("=", None, INVALID)},
    ],
    "XBRLI_DECIMALSUNION": [
        {"value": "INF", "expected": ("=", "=", VALID)},
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "invalid", "expected": ("=", None, INVALID)},
    ],
    "XBRLI_NONZERODECIMAL": NON_ZERO_DECIMAL_CASES + [
        {"value": "0", "expected": ("=", None, INVALID)},
        {"value": "0.0", "expected": ("=", None, INVALID)},
    ],
    "XBRLI_PRECISIONUNION": [
        {"value": "INF", "expected": ("=", "=", VALID)},
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "invalid", "expected": ("=", None, INVALID)},
    ],
    "xsd-pattern": [
        {"value": r"\c+", "expected": ("=", XsdPattern(xsdPattern=r"\c+", pyPattern=NMTOKENPattern), VALID)},
        {"value": r"\i\c*", "expected": ("=", XsdPattern(xsdPattern=r"\i\c*", pyPattern=namePattern), VALID)},
        {"value": r"[\i-[:]][\c-[:]]*", "expected": ("=", XsdPattern(xsdPattern=r"[\i-[:]][\c-[:]]*", pyPattern=NCNamePattern), VALID)},
        {"value": "test", "expected": ("=", XsdPattern.compile("test"), VALID)},
        {"value": r"invalid(", "expected": ("=", None, INVALID)},
        {"value": r"\(?", "expected": ("=", XsdPattern.compile(r"\(?"), VALID)},
        {"value": "foo(?=bar)", "expected": ("=", None, INVALID)},
        {"value": "(?:foo)", "expected": ("=", None, INVALID)},
    ],
}


def _generate_test_cases():
    test_cases = []
    for attrTag in [None, "attrTag"]:
        for isNillable in [False, True]:
            for isNil in [False, True]:
                for baseXsdType, cases in BASE_XSD_TYPES.items():
                    for case in cases:
                        expected = case.get("expected")
                        test_cases.append((
                            attrTag,
                            baseXsdType,
                            case.get("value"),
                            isNillable,
                            isNil,
                            case.get("facets"),
                            expected
                        ))
    return test_cases


def _assertValidateValue(actual, expected):
    if expected and isinstance(expected, float) and isnan(expected):
        assert isnan(actual)
    else:
        assert actual == expected


def _assertExpected(value: str, attrTag: str | None, elt: Any, expected: tuple, isNil: bool = False, isNillable: bool = False):
    expected = (
        value if expected[0] == "=" else expected[0],
        value if expected[1] == "=" else expected[1],
        expected[2]
    )
    if not value and isNil and isNillable:
        expected = (None, None, expected[2])
    if attrTag:
        attr = elt.xAttributes[attrTag]
        sValue = attr.sValue
        xValue = attr.xValue
        xValid = attr.xValid
    else:
        sValue = elt.sValue
        xValue = elt.xValue
        xValid = elt.xValid
    if expected[0] == nan:
        assert isnan(sValue)
    _assertValidateValue(sValue, expected[0])
    _assertValidateValue(xValue, expected[1])
    assert xValid == expected[2]


@pytest.mark.parametrize(
    "attrTag,baseXsdType,value,isNillable,isNil,facets,expected",
    [pytest.param(*testcase) for testcase in _generate_test_cases()],
)
def test_validateValue(attrTag: str, baseXsdType: str, value: str, isNillable: bool, isNil: bool, facets: dict, expected: tuple):
    elt = Mock(xAttributes={}, nsmap={"prefix": "namespaceURI"}, fractionValue=tuple(value.split("/")))
    validateValue(
        modelXbrl=Mock(),
        elt=elt,
        attrTag=attrTag,
        baseXsdType=baseXsdType,
        value=value,
        isNillable=isNillable,
        isNil=isNil,
        facets=facets)
    _assertExpected(
        value,
        attrTag,
        elt,
        expected,
        isNil,
        isNillable
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("valid1", ("=", "=", VALID)),
        pytest.param("invalid", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_enumeration(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "enumeration": {
            "valid1": None,
            "valid2": None,
            "valid3": None,
        }
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="string", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "base_xsd_type,member,value,expected_x_valid",
    [
        # dateTime: Z, +00:00 and -00:00 all denote UTC, so they are equal in the value
        # space even though their lexical forms differ.
        ("dateTime", "2002-01-01T12:01:01-00:00", "2002-01-01T12:01:01-00:00", VALID),  # lexical fast path
        ("dateTime", "2002-01-01T12:01:01-00:00", "2002-01-01T12:01:01Z", VALID),
        ("dateTime", "2002-01-01T12:01:01-00:00", "2002-01-01T12:01:01+00:00", VALID),
        ("dateTime", "2002-01-01T12:01:01-00:00", "2002-01-01T12:01:02+00:00", INVALID),  # different instant
        # date: timezone spellings that denote the same day are equal
        ("date", "2002-01-01-00:00", "2002-01-01Z", VALID),
        ("date", "2002-01-01-00:00", "2002-01-01+00:00", VALID),
        ("date", "2002-01-01-00:00", "2002-01-02Z", INVALID),
        # time: Z and -00:00 denote the same instant of day
        ("time", "12:00:00-00:00", "12:00:00Z", VALID),
        ("time", "12:00:00-00:00", "13:00:00Z", INVALID),
        # gYearMonth discards the timezone at parse time, so tz spellings collapse
        ("gYearMonth", "2002-01Z", "2002-01", VALID),
        ("gYearMonth", "2002-01Z", "2002-01+00:00", VALID),
        ("gYearMonth", "2002-01Z", "2002-02", INVALID),
        # duration: PT1H and PT60M are the same magnitude
        ("duration", "PT1H", "PT60M", VALID),
        ("duration", "PT1H", "PT61M", INVALID),
        # decimal: 1, 1.0 and 1.00 denote the same value
        ("decimal", "1", "1.0", VALID),
        ("decimal", "1", "1.00", VALID),
        ("decimal", "1", "2", INVALID),
        # float / double: scientific and trailing-zero spellings are equal
        ("float", "1", "1.0", VALID),
        ("float", "100", "1E2", VALID),
        ("float", "1", "2", INVALID),
        ("double", "1.5", "1.50", VALID),
        ("double", "1.5", "1.6", INVALID),
        # integer: leading sign and leading zeros are not part of the value
        ("integer", "1", "+1", VALID),
        ("integer", "1", "01", VALID),
        ("integer", "1", "2", INVALID),
        # boolean: {true, 1} and {false, 0}
        ("boolean", "1", "true", VALID),
        ("boolean", "1", "1", VALID),
        ("boolean", "1", "false", INVALID),
        ("boolean", "0", "false", VALID),
        ("boolean", "0", "true", INVALID),
    ],
)
def test_validateValueString_enumeration_value_space(
    base_xsd_type: str, member: str, value: str, expected_x_valid: int
):
    facets = {"enumeration": {member: None}}
    result = validateValueString(base_xsd_type, value, facets=facets, nsmap={"prefix": "namespaceURI"})
    assert result.xValid == expected_x_valid
    assert result.isXValid == (expected_x_valid >= VALID)


@pytest.mark.parametrize(
    "value,expected_x_valid",
    [
        ("1", VALID),      # exact lexical member (fast path)
        ("2", VALID),      # equals member "2.0" only in the value space
        ("3.0", VALID),    # equals member "3" only in the value space
        ("4", INVALID),    # not equal to any member
    ],
)
def test_validateValueString_enumeration_value_space_multiple_members(value: str, expected_x_valid: int):
    # a candidate may match any member, not just the first, by value-space equality
    facets = {"enumeration": {"1": None, "2.0": None, "3": None}}
    result = validateValueString("decimal", value, facets=facets)
    assert result.xValid == expected_x_valid


@pytest.mark.parametrize(
    "value,expected_x_valid",
    [
        ("p:local", VALID),   # same value as member "q:local" (both bound to urn:x)
        ("q:local", VALID),   # exact lexical member (fast path)
        ("p:other", INVALID), # different local name
    ],
)
def test_validateValueString_enumeration_qname_prefix_independent(value: str, expected_x_valid: int):
    # A QName's value is the (namespace, local name) pair, not its lexical prefix. With both
    # p: and q: bound to the same namespace in the instance, p:local and q:local are equal.
    facets = {"enumeration": {"q:local": None}}
    nsmap = {"p": "urn:x", "q": "urn:x"}
    result = validateValueString("QName", value, facets=facets, nsmap=nsmap)
    assert result.xValid == expected_x_valid


def test_validateValueString_enumeration_qname_uses_schema_facet_nsmap():
    # A QName-lexical member's namespace bindings are fixed at the schema (the facet element),
    # not the validated instance. The member prefix "s" is only bound on the facet element;
    # the instance binds the same namespace under a different prefix "i". Parsing the member
    # with the facet's own nsmap is what lets the instance value match.
    facetElt = Mock(nsmap={"s": "urn:x"})
    facets = {"enumeration": {"s:local": facetElt}}
    instanceNsmap = {"i": "urn:x"}
    match = validateValueString("QName", "i:local", facets=facets, nsmap=instanceNsmap)
    assert match.xValid == VALID
    mismatch = validateValueString("QName", "i:other", facets=facets, nsmap=instanceNsmap)
    assert mismatch.xValid == INVALID


def test_validateValueString_enumeration_value_space_is_lazily_cached():
    enumeration = _EnumerationFacet()
    enumeration["1"] = None
    facets = {"enumeration": enumeration}

    # The lexical fast path must not build the value-space cache at all.
    assert validateValueString("decimal", "1", facets=facets).xValid == VALID
    assert getattr(enumeration, "valueSpace", "unset") == "unset"

    # A lexical miss that matches in the value space builds and caches the map.
    assert validateValueString("decimal", "1.0", facets=facets).xValid == VALID
    cached = enumeration.valueSpace
    assert Decimal("1") in cached

    # A subsequent validation reuses the same cached object rather than rebuilding it.
    assert validateValueString("decimal", "1.00", facets=facets).xValid == VALID
    assert enumeration.valueSpace is cached


@pytest.mark.parametrize(
    "value,expected_x_valid",
    [
        ("1.0", VALID),    # matches the parseable member "1"
        ("2", INVALID),    # matches nothing; must not crash on the bad member
    ],
)
def test_validateValueString_enumeration_skips_unparseable_member(value: str, expected_x_valid: int):
    # A member that cannot be parsed as the datatype is skipped, not fatal.
    facets = {"enumeration": {"not-a-decimal": None, "1": None}}
    result = validateValueString("decimal", value, facets=facets)
    assert result.xValid == expected_x_valid


@pytest.mark.parametrize(
    "value,expected_x_valid",
    [
        ("1.0", VALID),
        ("3", INVALID),
    ],
)
def test_validateValueString_enumeration_set_valued(value: str, expected_x_valid: int):
    # Some enumerations are plain sets (no facet elements, no cache attribute); value-space
    # comparison must still work and the un-cacheable cache-write must be swallowed.
    facets = {"enumeration": {"1", "2"}}
    result = validateValueString("decimal", value, facets=facets)
    assert result.xValid == expected_x_valid


@pytest.mark.parametrize(
    "value,expected_x_valid",
    [
        ("p:a", VALID),    # exact lexical member (fast path, list value never compared)
        ("p:b", INVALID),  # lexical miss -> unhashable list xValue must not crash
    ],
)
def test_validateValueString_enumeration_unhashable_xvalue_does_not_crash(value: str, expected_x_valid: int):
    # enumerationQNames produces a list xValue, which is unhashable; the value-space lookup
    # must fall back to a linear scan instead of raising TypeError.
    facets = {"enumeration": {"p:a": None}}
    result = validateValueString("enumerationQNames", value, facets=facets, nsmap={"p": "urn:x"})
    assert result.xValid == expected_x_valid


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("123", ("=", "=", VALID)),
        pytest.param("1234", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_length(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "length": 3
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="string", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("123", ("=", "=", VALID)),
        pytest.param("12", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_minLength(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "minLength": 3
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="string", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("123", ("=", "=", VALID)),
        pytest.param("1234", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_maxLength(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "maxLength": 3
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="string", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "base_xsd_type,value,facets,expected_x_valid",
    [
        # length/minLength/maxLength are vacuous for QName and NOTATION: every value is
        # facet-valid with respect to them, regardless of the (prefix-dependent) lexical
        # length (Fix 5).
        ("QName", "prefix:localName", {"length": 5}, VALID),
        ("QName", "prefix:localName", {"minLength": 100}, VALID),
        ("QName", "prefix:localName", {"maxLength": 1}, VALID),
        ("NOTATION", "prefix:localName", {"length": 5}, VALID),
        ("NOTATION", "prefix:localName", {"minLength": 100}, VALID),
        ("NOTATION", "prefix:localName", {"maxLength": 1}, VALID),
        # control: length facets are still enforced for other types
        ("string", "abc", {"maxLength": 1}, INVALID),
        ("string", "abc", {"length": 3}, VALID),
    ],
)
def test_validateValueString_length_vacuous_for_qname_notation(
    base_xsd_type: str, value: str, facets: dict, expected_x_valid: int
):
    result = validateValueString(base_xsd_type, value, facets=facets, nsmap={"prefix": "namespaceURI"})
    assert result.xValid == expected_x_valid
    assert result.isXValid == (expected_x_valid >= VALID)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("ABC", ("=", "=", VALID)),
        pytest.param("abc", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_pattern(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "pattern": regex.compile(r"^([A-Z])*$")
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="string", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("1", (float(1), Decimal("1"), VALID)),
        pytest.param("1.01", (float(1.01), Decimal("1.01"), VALID)),
        pytest.param("100", (float(100), Decimal("100"), VALID)),
        pytest.param("1.001", ("=", None, INVALID)),
        # insignificant trailing zeros are not counted as significant digits.
        pytest.param("1.000", (float(1), Decimal("1.000"), VALID)),
        pytest.param("1000", ("=", None, INVALID)),
        # a leading sign is not a digit and must not be counted.
        pytest.param("-100", (float(-100), Decimal("-100"), VALID)),
        pytest.param("-1.01", (float(-1.01), Decimal("-1.01"), VALID)),
        pytest.param("-1000", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_totalDigits(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "totalDigits": 3
    }
    # totalDigits only applies to xs:decimal (and its derived types); it isn't a valid
    # constraining facet for xs:float/xs:double.
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="decimal", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize("base_xsd_type", ["float", "double"])
def test_validateValue_facets_totalDigits_not_applicable_to_float(base_xsd_type: str):
    # totalDigits isn't a valid constraining facet for xs:float/xs:double, so a value
    # with more digits than totalDigits allows must still be valid.
    elt = Mock()
    facets = {
        "totalDigits": 1
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType=base_xsd_type, value="123.456", facets=facets)
    assert elt.xValid == VALID
    assert elt.xValue == float("123.456")


@pytest.mark.parametrize(
    "base_xsd_type,value,total_digits,expected_x_valid",
    [
        # the integer branch and the decimal branch both exclude the sign.
        ("integer", "-6", 1, VALID),
        ("integer", "6", 1, VALID),
        ("integer", "-66", 1, INVALID),
        ("integer", "-66", 2, VALID),
        ("decimal", "-1.5", 2, VALID),
        ("decimal", "+1.5", 2, VALID),
        ("decimal", "-1.55", 2, INVALID),
        # insignificant zeros (leading or trailing) are not counted as significant digits.
        ("decimal", "-1.50", 2, VALID),
        ("decimal", "0001.5", 2, VALID),
        ("decimal", "0.001", 1, VALID),
    ],
)
def test_validateValueString_totalDigits_excludes_sign(
    base_xsd_type: str, value: str, total_digits: int, expected_x_valid: int
):
    result = validateValueString(base_xsd_type, value, facets={"totalDigits": total_digits})
    assert result.xValid == expected_x_valid
    assert result.isXValid == (expected_x_valid >= VALID)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("1", (float(1), float(1), VALID)),
        pytest.param("1.01", (float(1.01), float(1.01), VALID)),
        pytest.param("1.001", (float(1.001), float(1.001), VALID)),
        pytest.param("1.000", (float(1), float(1), VALID)),
        pytest.param("1000", (float(1000), float(1000), VALID)),
        pytest.param("1.0001", ("=", None, INVALID)),
        pytest.param("1.0000", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_fractionDigits(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "fractionDigits": 3
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="float", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("-1", ("=", None, INVALID)),
        pytest.param("0", (float(0), float(0), VALID)),
        pytest.param("1", (float(1), float(1), VALID)),
        pytest.param("2", (float(2), float(2), VALID)),
        pytest.param("3", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_minMaxInclusive(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "minInclusive": 0,
        "maxInclusive": 2
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="float", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "value,expected",
    [
        pytest.param("-1", ("=", None, INVALID)),
        pytest.param("0", ("=", None, INVALID)),
        pytest.param("1", (float(1), float(1), VALID)),
        pytest.param("2", ("=", None, INVALID)),
        pytest.param("3", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_minMaxExclusive(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "minExclusive": 0,
        "maxExclusive": 2
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="float", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


@pytest.mark.parametrize(
    "base_xsd_type,value,facets,expected_x_valid",
    [
        # date: the four bounding facets are enforced in the value space; on the
        # bound itself the inclusive variants accept and the exclusive variants reject.
        ("date", "2009-01-01", {"maxExclusive": DateTime(2011, 10, 16)}, VALID),
        ("date", "2011-10-16", {"maxExclusive": DateTime(2011, 10, 16)}, INVALID),
        ("date", "2027-07-04", {"maxExclusive": DateTime(2011, 10, 16)}, INVALID),
        ("date", "2009-01-01", {"maxInclusive": DateTime(2011, 10, 16)}, VALID),
        ("date", "2011-10-16", {"maxInclusive": DateTime(2011, 10, 16)}, VALID),
        ("date", "2027-07-04", {"maxInclusive": DateTime(2011, 10, 16)}, INVALID),
        ("date", "2027-07-04", {"minInclusive": DateTime(2011, 10, 16)}, VALID),
        ("date", "2011-10-16", {"minInclusive": DateTime(2011, 10, 16)}, VALID),
        ("date", "2009-01-01", {"minInclusive": DateTime(2011, 10, 16)}, INVALID),
        ("date", "2027-07-04", {"minExclusive": DateTime(2011, 10, 16)}, VALID),
        ("date", "2011-10-16", {"minExclusive": DateTime(2011, 10, 16)}, INVALID),
        ("date", "2009-01-01", {"minExclusive": DateTime(2011, 10, 16)}, INVALID),
        # dateTime
        ("dateTime", "2025-01-02T03:04:05", {"maxInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, VALID),
        ("dateTime", "2025-01-02T03:04:06", {"maxInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, INVALID),
        # time (Time, a datetime.time subclass)
        ("time", "03:04:04", {"maxInclusive": Time(3, 4, 5)}, VALID),
        ("time", "03:04:05", {"maxInclusive": Time(3, 4, 5)}, VALID),
        ("time", "03:04:06", {"maxInclusive": Time(3, 4, 5)}, INVALID),
        ("time", "03:04:05", {"maxExclusive": Time(3, 4, 5)}, INVALID),
        ("time", "03:04:05", {"minExclusive": Time(3, 4, 5)}, INVALID),
        ("time", "03:04:06", {"minExclusive": Time(3, 4, 5)}, VALID),
        # gYear
        ("gYear", "0001", {"maxInclusive": gYear(5)}, VALID),
        ("gYear", "0009", {"maxInclusive": gYear(5)}, INVALID),
        # gYearMonth
        ("gYearMonth", "2010-12", {"maxInclusive": gYearMonth(2011, 1)}, VALID),
        ("gYearMonth", "2011-01", {"maxExclusive": gYearMonth(2011, 1)}, INVALID),
        ("gYearMonth", "2011-02", {"maxInclusive": gYearMonth(2011, 1)}, INVALID),
        # gMonth (gMonth)
        ("gMonth", "--05", {"maxInclusive": gMonth(6)}, VALID),
        ("gMonth", "--06", {"maxExclusive": gMonth(6)}, INVALID),
        ("gMonth", "--05", {"minInclusive": gMonth(6)}, INVALID),
        ("gMonth", "--07", {"minExclusive": gMonth(6)}, VALID),
        # gMonthDay (gMonthDay)
        ("gMonthDay", "--06-14", {"maxInclusive": gMonthDay(6, 15)}, VALID),
        ("gMonthDay", "--06-16", {"maxInclusive": gMonthDay(6, 15)}, INVALID),
        ("gMonthDay", "--06-15", {"minExclusive": gMonthDay(6, 15)}, INVALID),
        ("gMonthDay", "--06-16", {"minInclusive": gMonthDay(6, 15)}, VALID),
        # gDay (gDay)
        ("gDay", "---14", {"maxInclusive": gDay(15)}, VALID),
        ("gDay", "---16", {"maxInclusive": gDay(15)}, INVALID),
        ("gDay", "---15", {"minExclusive": gDay(15)}, INVALID),
        ("gDay", "---16", {"minInclusive": gDay(15)}, VALID),
        # duration whose bounds differ in the years/months/days part (not the seconds
        # tie-break)
        ("duration", "P6M", {"maxExclusive": isoDuration("P1Y")}, VALID),
        ("duration", "P2Y", {"maxExclusive": isoDuration("P1Y")}, INVALID),
    ],
)
def test_validateValueString_facets_ordering(
    base_xsd_type: str, value: str, facets: dict, expected_x_valid: int
):
    result = validateValueString(base_xsd_type, value, facets=facets)
    assert result.xValid == expected_x_valid
    assert result.isXValid == (expected_x_valid >= VALID)


@pytest.mark.parametrize(
    "base_xsd_type,value,facets,expected_x_valid",
    [
        # Ordering an xs:date/time value against a bound where exactly one side carries a
        # timezone must not crash (Python refuses to order offset-naive vs offset-aware
        # datetimes/times). Per XSD Datatypes 3.2.7.4 the absent timezone ranges over
        # +/-14:00: when that uncertainty straddles the bound the order is indeterminate,
        # and per Datatypes 3.2.6.3 ("indeterminate comparisons should be considered as
        # 'false'") the facet is not satisfied, so the value is rejected. Only a value
        # provably more than 14h beyond the bound, on the satisfying side, is a
        # determinate acceptance; provably beyond it on the other side is a determinate
        # violation.
        # timezone-aware value vs timezone-naive bound
        ("dateTime", "2025-01-02T03:04:05Z", {"maxInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, INVALID),  # indeterminate
        ("dateTime", "2025-01-02T03:04:05Z", {"minInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, INVALID),  # indeterminate
        ("dateTime", "2025-01-04T00:00:00Z", {"maxInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, INVALID),  # determinate violation
        ("dateTime", "2024-12-31T00:00:00Z", {"minInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, INVALID),  # determinate violation
        ("dateTime", "2025-01-05T00:00:00Z", {"minInclusive": DateTime(2025, 1, 2, 3, 4, 5)}, VALID),  # determinate acceptance
        # timezone-naive value vs timezone-aware bound
        ("dateTime", "2025-01-02T03:04:05", {"maxInclusive": DateTime(2025, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)}, INVALID),  # indeterminate
        ("dateTime", "2024-12-31T00:00:00", {"minInclusive": DateTime(2025, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)}, INVALID),  # determinate violation
        ("dateTime", "2025-01-01T00:00:00", {"maxInclusive": DateTime(2025, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)}, VALID),  # determinate acceptance
        # xs:time (no date component) with mixed timezone presence
        ("time", "03:04:05", {"maxInclusive": Time(3, 4, 5, tzinfo=datetime.timezone.utc)}, INVALID),  # indeterminate
        ("time", "03:04:05Z", {"minInclusive": Time(3, 4, 5)}, INVALID),  # indeterminate
        ("time", "23:00:00Z", {"minInclusive": Time(0, 0, 0)}, VALID),  # determinate acceptance
        ("time", "00:00:00", {"maxInclusive": Time(23, 0, 0, tzinfo=datetime.timezone.utc)}, VALID),  # determinate acceptance
    ],
)
def test_validateValueString_facets_ordering_timezone(
    base_xsd_type: str, value: str, facets: dict, expected_x_valid: int
):
    result = validateValueString(base_xsd_type, value, facets=facets)
    assert result.xValid == expected_x_valid
    assert result.isXValid == (expected_x_valid >= VALID)


@pytest.mark.parametrize(
    "whitespace,value,expected",
    [
        pytest.param("preserve", "\t\tA  B\n\nC ", ("=", "=", VALID)),
        pytest.param("replace", "\t\tA  B\n\nC ", ("  A  B  C ", "  A  B  C ", VALID)),
        pytest.param("collapse", "\t\tA  B\n\nC ", ("A B C", "A B C", VALID)),
    ],
)
def test_validateValue_facets_whitespace(whitespace: str, value: str, expected: tuple):
    elt = Mock()
    facets = {
        "whiteSpace": whitespace
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="string", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


NSMAP = {"prefix": "namespaceURI"}
_SKIP_TYPES_FOR_VALUE_STRING = {None, "fraction"}


def _generate_value_string_test_cases():
    test_cases = []
    for isNillable in [False, True]:
        for isNil in [False, True]:
            for baseXsdType, cases in BASE_XSD_TYPES.items():
                if baseXsdType in _SKIP_TYPES_FOR_VALUE_STRING:
                    continue
                for case in cases:
                    test_cases.append(
                        (
                            baseXsdType,
                            case.get("value"),
                            isNillable,
                            isNil,
                            case.get("facets"),
                            case.get("expected"),
                        )
                    )
    return test_cases


@pytest.mark.parametrize(
    "baseXsdType,value,isNillable,isNil,facets,expected",
    [pytest.param(*testcase) for testcase in _generate_value_string_test_cases()],
)
def test_validateValueString(
    baseXsdType: str, value: str, isNillable: bool, isNil: bool, facets: dict, expected: tuple
):
    expectedXValid = expected[2]
    result = validateValueString(
        baseXsdType=baseXsdType,
        value=value,
        isNillable=isNillable,
        isNil=isNil,
        facets=facets,
        nsmap=NSMAP,
    )
    assert result.xValid == expectedXValid
    if expectedXValid == INVALID:
        assert result.sValue == value
        return
    expectedSValue = value if expected[0] == "=" else expected[0]
    expectedXValue = value if expected[1] == "=" else expected[1]
    if not value and isNil and isNillable:
        expectedSValue = None
        expectedXValue = None
    if expectedSValue == nan:
        assert isnan(result.sValue)
    else:
        _assertValidateValue(result.sValue, expectedSValue)
    _assertValidateValue(result.xValue, expectedXValue)
    assert result.xValid == expectedXValid
    assert result.isXValid == (expectedXValid >= VALID)


class TestXsdPatternNameEscapes:
    @pytest.mark.parametrize(
        "pattern,value,expected_match",
        [
            (r"\i\c*", ":foo", True),
            (r"[\i-[:]][\c-[:]]*", ":foo", False),
        ],
    )
    def test_leading_colon(self, pattern: str, value: str, expected_match: bool):
        compiled = XsdPattern.compile(pattern)
        assert (compiled.match(value) is not None) == expected_match


class TestValidateFacetValueString:
    def test_length(self):
        result = validateFacetValueString("length", "3", "string")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 3

    def test_length_invalid(self):
        result = validateFacetValueString("length", "abc", "string")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_minLength(self):
        result = validateFacetValueString("minLength", "1", "string")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 1

    def test_minLength_invalid(self):
        result = validateFacetValueString("minLength", "abc", "string")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_maxLength(self):
        result = validateFacetValueString("maxLength", "10", "string")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 10

    def test_maxLength_invalid(self):
        result = validateFacetValueString("maxLength", "abc", "string")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_totalDigits(self):
        result = validateFacetValueString("totalDigits", "5", "decimal")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 5

    def test_totalDigits_invalid(self):
        result = validateFacetValueString("totalDigits", "abc", "decimal")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_fractionDigits(self):
        result = validateFacetValueString("fractionDigits", "2", "decimal")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 2

    def test_fractionDigits_invalid(self):
        result = validateFacetValueString("fractionDigits", "abc", "decimal")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_minInclusive(self):
        result = validateFacetValueString("minInclusive", "0", "integer")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 0

    def test_minInclusive_invalid(self):
        result = validateFacetValueString("minInclusive", "abc", "integer")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_maxInclusive(self):
        result = validateFacetValueString("maxInclusive", "100", "integer")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 100

    def test_maxInclusive_invalid(self):
        result = validateFacetValueString("maxInclusive", "abc", "integer")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_minExclusive(self):
        result = validateFacetValueString("minExclusive", "-1", "integer")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == -1

    def test_minExclusive_invalid(self):
        result = validateFacetValueString("minExclusive", "abc", "integer")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_maxExclusive(self):
        result = validateFacetValueString("maxExclusive", "50", "integer")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.xValue == 50

    def test_maxExclusive_invalid(self):
        result = validateFacetValueString("maxExclusive", "abc", "integer")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "abc"
        assert result.xValue is None

    def test_whiteSpace(self):
        result = validateFacetValueString("whiteSpace", "collapse", "string")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.sValue == "collapse"
        assert result.xValue == "collapse"

    def test_pattern(self):
        result = validateFacetValueString("pattern", "[A-Z]+", "string")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.sValue == "[A-Z]+"
        assert isinstance(result.xValue, XsdPattern)

    def test_pattern_invalid(self):
        result = validateFacetValueString("pattern", "invalid(", "string")
        assert result.xValid == INVALID
        assert not result.isXValid
        assert result.sValue == "invalid("
        assert result.xValue is None

    def test_unknown_facet(self):
        result = validateFacetValueString("unknownFacet", "value", "string")
        assert result.xValid == VALID
        assert result.isXValid
        assert result.sValue == "value"
        assert result.xValue == "value"

    @pytest.mark.parametrize(
        "base_xsd_type,value,expected_x_valid",
        [
            ("int", "2147483647", VALID),
            ("int", "-2147483648", VALID),
            ("int", "2147483648", INVALID),
            ("int", "-2147483649", INVALID),
            ("long", "9223372036854775807", VALID),
            ("long", "-9223372036854775808", VALID),
            ("long", "9223372036854775808", INVALID),
            ("long", "-9223372036854775809", INVALID),
            ("unsignedInt", "4294967295", VALID),
            ("unsignedInt", "0", VALID),
            ("unsignedInt", "4294967296", INVALID),
            ("unsignedInt", "-1", INVALID),
            ("unsignedLong", "18446744073709551615", VALID),
            ("unsignedLong", "0", VALID),
            ("unsignedLong", "18446744073709551616", INVALID),
            ("unsignedLong", "-1", INVALID),
            ("negativeInteger", "-1", VALID),
            ("negativeInteger", "-1000", VALID),
            ("negativeInteger", "0", INVALID),
            ("negativeInteger", "1", INVALID),
        ],
    )
    def test_bounds_facet_type_range(self, base_xsd_type: str, value: str, expected_x_valid: int):
        result = validateFacetValueString("minInclusive", value, base_xsd_type)
        assert result.xValid == expected_x_valid
        assert result.isXValid == (expected_x_valid >= VALID)

    @pytest.mark.parametrize(
        "facet_name,value,expected_x_valid",
        [
            ("length", "0", VALID),
            ("length", "-1", INVALID),
            ("minLength", "0", VALID),
            ("minLength", "-1", INVALID),
            ("maxLength", "0", VALID),
            ("maxLength", "-1", INVALID),
            ("fractionDigits", "0", VALID),
            ("fractionDigits", "-1", INVALID),
            ("totalDigits", "1", VALID),
            ("totalDigits", "0", INVALID),
        ],
    )
    def test_numeric_facet_bounds(self, facet_name: str, value: str, expected_x_valid: int):
        result = validateFacetValueString(facet_name, value, "string")
        assert result.xValid == expected_x_valid
        assert result.isXValid == (expected_x_valid >= VALID)

    @pytest.mark.parametrize(
        "facet_name,base_xsd_type,value,expected_x_valid",
        [
            ("minExclusive", "byte", "126", VALID),
            ("minExclusive", "byte", "127", INVALID),
            ("minExclusive", "byte", "0", VALID),
            ("minExclusive", "short", "32766", VALID),
            ("minExclusive", "short", "32767", INVALID),
            ("minExclusive", "int", "2147483646", VALID),
            ("minExclusive", "int", "2147483647", INVALID),
            ("minExclusive", "long", "9223372036854775806", VALID),
            ("minExclusive", "long", "9223372036854775807", INVALID),
            ("minExclusive", "unsignedByte", "254", VALID),
            ("minExclusive", "unsignedByte", "255", INVALID),
            ("minExclusive", "unsignedShort", "65534", VALID),
            ("minExclusive", "unsignedShort", "65535", INVALID),
            ("minExclusive", "unsignedInt", "4294967294", VALID),
            ("minExclusive", "unsignedInt", "4294967295", INVALID),
            ("minExclusive", "unsignedLong", "18446744073709551614", VALID),
            ("minExclusive", "unsignedLong", "18446744073709551615", INVALID),
            ("minExclusive", "negativeInteger", "-2", VALID),
            ("minExclusive", "negativeInteger", "-1", INVALID),
            ("minExclusive", "nonPositiveInteger", "-1", VALID),
            ("minExclusive", "nonPositiveInteger", "0", INVALID),
            ("maxExclusive", "byte", "-127", VALID),
            ("maxExclusive", "byte", "-128", INVALID),
            ("maxExclusive", "byte", "0", VALID),
            ("maxExclusive", "short", "-32767", VALID),
            ("maxExclusive", "short", "-32768", INVALID),
            ("maxExclusive", "int", "-2147483647", VALID),
            ("maxExclusive", "int", "-2147483648", INVALID),
            ("maxExclusive", "long", "-9223372036854775807", VALID),
            ("maxExclusive", "long", "-9223372036854775808", INVALID),
            ("maxExclusive", "unsignedByte", "1", VALID),
            ("maxExclusive", "unsignedByte", "0", INVALID),
            ("maxExclusive", "unsignedShort", "1", VALID),
            ("maxExclusive", "unsignedShort", "0", INVALID),
            ("maxExclusive", "unsignedInt", "1", VALID),
            ("maxExclusive", "unsignedInt", "0", INVALID),
            ("maxExclusive", "unsignedLong", "1", VALID),
            ("maxExclusive", "unsignedLong", "0", INVALID),
            ("maxExclusive", "positiveInteger", "2", VALID),
            ("maxExclusive", "positiveInteger", "1", INVALID),
            ("maxExclusive", "nonNegativeInteger", "1", VALID),
            ("maxExclusive", "nonNegativeInteger", "0", INVALID),
            ("minExclusive", "positiveInteger", "5", VALID),
            ("minExclusive", "nonNegativeInteger", "5", VALID),
            ("minExclusive", "integer", "5", VALID),
            ("maxExclusive", "negativeInteger", "-5", VALID),
            ("maxExclusive", "nonPositiveInteger", "-5", VALID),
            ("maxExclusive", "integer", "5", VALID),
        ],
    )
    def test_exclusive_bounds_facet_type_range(
        self, facet_name: str, base_xsd_type: str, value: str, expected_x_valid: int
    ):
        result = validateFacetValueString(facet_name, value, base_xsd_type)
        assert result.xValid == expected_x_valid
        assert result.isXValid == (expected_x_valid >= VALID)

    @pytest.mark.parametrize(
        "base_xsd_type,value,expected_x_valid",
        [
            ("decimal", "0", VALID),
            ("decimal", "3", VALID),
            ("integer", "0", VALID),
            ("integer", "1", INVALID),
            ("byte", "0", VALID),
            ("byte", "1", INVALID),
            ("short", "0", VALID),
            ("short", "1", INVALID),
            ("int", "0", VALID),
            ("int", "1", INVALID),
            ("long", "0", VALID),
            ("long", "1", INVALID),
            ("unsignedByte", "0", VALID),
            ("unsignedByte", "1", INVALID),
            ("unsignedShort", "0", VALID),
            ("unsignedShort", "1", INVALID),
            ("unsignedInt", "0", VALID),
            ("unsignedInt", "1", INVALID),
            ("unsignedLong", "0", VALID),
            ("unsignedLong", "1", INVALID),
            ("negativeInteger", "0", VALID),
            ("negativeInteger", "1", INVALID),
            ("nonNegativeInteger", "0", VALID),
            ("nonNegativeInteger", "1", INVALID),
            ("nonPositiveInteger", "0", VALID),
            ("nonPositiveInteger", "1", INVALID),
            ("positiveInteger", "0", VALID),
            ("positiveInteger", "1", INVALID),
        ],
    )
    def test_fractionDigits_facet_integer_types(self, base_xsd_type: str, value: str, expected_x_valid: int):
        result = validateFacetValueString("fractionDigits", value, base_xsd_type)
        assert result.xValid == expected_x_valid
        assert result.isXValid == (expected_x_valid >= VALID)


class TestBase64BinaryValidation:
    @pytest.mark.parametrize("value", [
        "",
        "AAAA",
        "AA==",
        "AAA=",
        "AAAAAAAA",
        "dGVzdA==",
        "A A A A",
    ])
    def test_valid_base64_binary(self, value: str):
        result = validateValueString("base64Binary", value)
        assert result.xValid == VALID
        assert result.isXValid

    @pytest.mark.parametrize("value", [
        "AAAAA",
        "!!!!",
        "AAA",
        "AA=A",
        "====",
        "A",
    ])
    def test_invalid_base64_binary(self, value: str):
        result = validateValueString("base64Binary", value)
        assert result.xValid == INVALID
        assert not result.isXValid

    @pytest.mark.parametrize("value,facet,length,expected_x_valid", [
        # length facets count octets of decoded data, not lexical characters:
        # "YQ==" is 4 characters but decodes to the single octet 0x61.
        ("YQ==", "length", 1, VALID),
        ("YQ==", "length", 4, INVALID),
        ("YQ==", "maxLength", 1, VALID),
        ("YQ==", "minLength", 2, INVALID),
        ("YWI=", "length", 2, VALID),  # "ab"
        ("YWJj", "length", 3, VALID),  # "abc"
        ("A A A A", "length", 3, VALID),  # lexical whitespace ignored -> AAAA -> 3 octets
    ])
    def test_length_facets_count_octets(self, value: str, facet: str, length: int, expected_x_valid: int):
        result = validateValueString("base64Binary", value, facets={facet: length})
        assert result.xValid == expected_x_valid
        assert result.isXValid == (expected_x_valid >= VALID)


class TestHexBinaryValidation:
    @pytest.mark.parametrize("value", [
        "",
        "FF",
        "00",
        "AABB",
        "ff",
        "aAbBcCdDeEfF",
        "0123456789ABCDEF",
    ])
    def test_valid_hex_binary(self, value: str):
        result = validateValueString("hexBinary", value)
        assert result.xValid == VALID
        assert result.isXValid

    @pytest.mark.parametrize("value", [
        "F",
        "FFF",
        "GG",
        "FF-AA",
        "0xFF",
        "FFGG",
    ])
    def test_invalid_hex_binary(self, value: str):
        result = validateValueString("hexBinary", value)
        assert result.xValid == INVALID
        assert not result.isXValid

    @pytest.mark.parametrize("value,facet,length,expected_x_valid", [
        # length facets count octets, not hex digits: two hex digits = one octet.
        ("FF", "length", 1, VALID),
        ("48656C6C6F", "length", 5, VALID),  # "Hello"
        ("48656C6C6F", "length", 10, INVALID),
        ("AABB", "maxLength", 2, VALID),
        ("AABB", "maxLength", 1, INVALID),
        ("FF", "minLength", 2, INVALID),
    ])
    def test_length_facets_count_octets(self, value: str, facet: str, length: int, expected_x_valid: int):
        result = validateValueString("hexBinary", value, facets={facet: length})
        assert result.xValid == expected_x_valid
        assert result.isXValid == (expected_x_valid >= VALID)


class TestTimezoneValidation:
    @pytest.mark.parametrize(
        "base_xsd_type,value",
        [
            ("date", "2024-01-01"),
            ("date", "2024-01-01Z"),
            ("date", "2024-01-01+00:00"),
            ("date", "2024-01-01-05:00"),
            ("date", "2024-01-01+14:00"),
            ("date", "2024-01-01-14:00"),
            ("dateTime", "2024-01-01T00:00:00"),
            ("dateTime", "2024-01-01T00:00:00Z"),
            ("dateTime", "2024-01-01T00:00:00+05:30"),
            ("dateTime", "2024-01-01T00:00:00-14:00"),
            ("time", "12:00:00"),
            ("time", "12:00:00Z"),
            ("time", "12:00:00+14:00"),
        ],
    )
    def test_valid_timezone(self, base_xsd_type: str, value: str):
        result = validateValueString(base_xsd_type, value)
        assert result.xValid == VALID
        assert result.isXValid

    @pytest.mark.parametrize(
        "base_xsd_type,value",
        [
            ("date", "2024-01-01+15:00"),
            ("date", "2024-01-01-15:00"),
            ("date", "2024-01-01+14:01"),
            ("date", "2024-01-01-14:01"),
            ("date", "2024-01-01+05:69"),
            ("dateTime", "2024-01-01T00:00:00+15:00"),
            ("dateTime", "2024-01-01T00:00:00+14:01"),
            ("dateTime", "2024-01-01T00:00:00+05:69"),
            ("time", "12:00:00+15:00"),
            ("time", "12:00:00+14:01"),
        ],
    )
    def test_invalid_timezone(self, base_xsd_type: str, value: str):
        result = validateValueString(base_xsd_type, value)
        assert result.xValid == INVALID
        assert not result.isXValid


class TestIsoDurationComparison(TestCase):
    def test_gt_non_iso_duration(self):
        with self.assertRaises(TypeError):
            _ = isoDuration("P1Y2M3DT10H36M30S") > DateTime(2025, 1, 2)

    def test_gt_seconds_tiebreak_when_dates_equal(self):
        # equal years/months/days; the value with greater seconds must compare greater
        # via the seconds tie-break.
        assert isoDuration("P1Y2M3DT10H36M30S") > isoDuration("P1Y2M3DT10H36M29S")

    def test_not_gt_when_equal(self):
        assert not (isoDuration("P1Y2M3DT10H36M29S") > isoDuration("P1Y2M3DT10H36M29S"))

    def test_not_gt_when_seconds_less(self):
        assert not (isoDuration("P1Y2M3DT10H36M28S") > isoDuration("P1Y2M3DT10H36M29S"))

    def test_gt_when_avgdays_greater(self):
        assert isoDuration("P2Y") > isoDuration("P1Y")

    def test_ge_uses_gt(self):
        assert isoDuration("P1Y2M3DT10H36M30S") >= isoDuration("P1Y2M3DT10H36M29S")
        assert isoDuration("P1Y2M3DT10H36M29S") >= isoDuration("P1Y2M3DT10H36M29S")

    def test_lt_non_iso_duration(self):
        with self.assertRaises(TypeError):
            _ = isoDuration("P1Y2M3DT10H36M30S") < DateTime(2025, 1, 2)

    def test_lt_seconds_tiebreak_when_dates_equal(self):
        # equal years/months/days; the value with greater seconds must compare greater
        # via the seconds tie-break.
        assert isoDuration("P1Y2M3DT10H36M29S") < isoDuration("P1Y2M3DT10H36M30S")

    def test_not_lt_when_equal(self):
        assert not (isoDuration("P1Y2M3DT10H36M29S") < isoDuration("P1Y2M3DT10H36M29S"))

    def test_not_lt_when_seconds_greater(self):
        assert not (isoDuration("P1Y2M3DT10H36M29S") < isoDuration("P1Y2M3DT10H36M28S"))

    def test_lt_when_avgdays_less(self):
        assert isoDuration("P1Y") < isoDuration("P2Y")

    def test_le_uses_lt(self):
        assert isoDuration("P1Y2M3DT10H36M29S") <= isoDuration("P1Y2M3DT10H36M30S")
        assert isoDuration("P1Y2M3DT10H36M29S") <= isoDuration("P1Y2M3DT10H36M29S")
