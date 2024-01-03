from __future__ import annotations

import datetime
from _decimal import Decimal
from fractions import Fraction
from math import inf, nan, isnan
from typing import Any

import pytest
import regex
from unittest.mock import Mock

from arelle.ModelValue import QName, DateTime, Time, isoDuration, gDay, gMonth, gMonthDay, gYear, gYearMonth
from arelle.XmlValidate import validateValue, VALID, UNKNOWN, INVALID, VALID_ID, NMTOKENPattern, namePattern, NCNamePattern, VALID_NO_CONTENT

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
        {"value": ":invalid:", "expected": ("=", "=", VALID)},
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
        {"value": "126", "expected": (126, 126, VALID)},
        {"value": "127", "expected": ("=", None, INVALID)},  # TODO: This and other integer ranges seem to incorrectly exclude the maximum value
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
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
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
        {"value": "-1", "expected": (-1, -1, VALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
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
        {"value": "0", "expected": (0, 0, VALID)},  # TODO: should be invalid
        {"value": "1", "expected": (1, 1, VALID)},  # TODO: should be invalid
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
        {"value": "32766", "expected": (32766, 32766, VALID)},
        {"value": "32767", "expected": ("=", None, INVALID)},
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
        {"value": "254", "expected": (254, 254, VALID)},
        {"value": "255", "expected": ("=", None, INVALID)},
    ],
    "unsignedInt": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
    ],
    "unsignedLong": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
    ],
    "unsignedShort": [
        {"value": "-1", "expected": ("=", None, INVALID)},
        {"value": "0", "expected": (0, 0, VALID)},
        {"value": "1", "expected": (1, 1, VALID)},
        {"value": "65534", "expected": (65534, 65534, VALID)},
        {"value": "65535", "expected": ("=", None, INVALID)},
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
        {"value": r"\c+", "expected": ("=", NMTOKENPattern, VALID)},
        {"value": r"\i\c*", "expected": ("=", namePattern, VALID)},
        {"value": r"[\i-[:]][\c-[:]]*", "expected": ("=", NCNamePattern, VALID)},
        # {"value": "test", "expected": ("=", XsdPattern().compile("test"), VALID)},  # TODO: XsdPattern equality not working
        {"value": r"invalid(", "expected": ("=", None, INVALID)},
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
