from __future__ import annotations

import datetime
from _decimal import Decimal
from fractions import Fraction
from math import inf, isnan, nan
from typing import Any
from unittest.mock import Mock

import pytest
import regex

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
        {"value": ":invalid:", "expected": ("=", None, INVALID)},
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
    ],
    "NCName": [
        {"value": "*invalid", "expected": ("=", None, INVALID)},
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
        pytest.param("1", (float(1), float(1), VALID)),
        pytest.param("1.01", (float(1.01), float(1.01), VALID)),
        pytest.param("100", (float(100), float(100), VALID)),
        pytest.param("1.001", ("=", None, INVALID)),
        pytest.param("1.000", ("=", None, INVALID)),
        pytest.param("1000", ("=", None, INVALID)),
    ],
)
def test_validateValue_facets_totalDigits(value: str, expected: tuple):
    elt = Mock()
    facets = {
        "totalDigits": 3
    }
    validateValue(modelXbrl=Mock(), elt=elt, attrTag=None, baseXsdType="float", value=value, facets=facets)
    _assertExpected(value, attrTag=None, elt=elt, expected=expected)


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
