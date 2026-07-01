"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from types import MappingProxyType

from arelle import XbrlConst
from arelle.ModelValue import QName


def _xs_qname(name: str) -> QName:
    return QName("xs", XbrlConst.xsd, name)


ANY_URI = _xs_qname("anyURI")
BASE64_BINARY = _xs_qname("base64Binary")
BOOLEAN = _xs_qname("boolean")
BYTE = _xs_qname("byte")
DATE = _xs_qname("date")
DATE_TIME = _xs_qname("dateTime")
DECIMAL = _xs_qname("decimal")
DOUBLE = _xs_qname("double")
DURATION = _xs_qname("duration")
FLOAT = _xs_qname("float")
G_DAY = _xs_qname("gDay")
G_MONTH = _xs_qname("gMonth")
G_MONTH_DAY = _xs_qname("gMonthDay")
G_YEAR = _xs_qname("gYear")
G_YEAR_MONTH = _xs_qname("gYearMonth")
HEX_BINARY = _xs_qname("hexBinary")
INT = _xs_qname("int")
INTEGER = _xs_qname("integer")
LANGUAGE = _xs_qname("language")
LONG = _xs_qname("long")
NAME = _xs_qname("Name")
NC_NAME = _xs_qname("NCName")
NEGATIVE_INTEGER = _xs_qname("negativeInteger")
NON_NEGATIVE_INTEGER = _xs_qname("nonNegativeInteger")
NON_POSITIVE_INTEGER = _xs_qname("nonPositiveInteger")
NORMALIZED_STRING = _xs_qname("normalizedString")
POSITIVE_INTEGER = _xs_qname("positiveInteger")
QNAME = _xs_qname("QName")
SHORT = _xs_qname("short")
STRING = _xs_qname("string")
TIME = _xs_qname("time")
TOKEN = _xs_qname("token")
UNSIGNED_BYTE = _xs_qname("unsignedByte")
UNSIGNED_INT = _xs_qname("unsignedInt")
UNSIGNED_LONG = _xs_qname("unsignedLong")
UNSIGNED_SHORT = _xs_qname("unsignedShort")

_TC_PERMITTED_SCHEMA_TYPES: Set[QName] = frozenset(
    {
        ANY_URI,
        BASE64_BINARY,
        BOOLEAN,
        BYTE,
        DATE,
        DATE_TIME,
        DECIMAL,
        DOUBLE,
        DURATION,
        FLOAT,
        G_DAY,
        G_MONTH,
        G_MONTH_DAY,
        G_YEAR,
        G_YEAR_MONTH,
        HEX_BINARY,
        INT,
        INTEGER,
        LANGUAGE,
        LONG,
        NAME,
        NC_NAME,
        NEGATIVE_INTEGER,
        NON_NEGATIVE_INTEGER,
        NON_POSITIVE_INTEGER,
        NORMALIZED_STRING,
        POSITIVE_INTEGER,
        QNAME,
        SHORT,
        STRING,
        TIME,
        TOKEN,
        UNSIGNED_BYTE,
        UNSIGNED_INT,
        UNSIGNED_LONG,
        UNSIGNED_SHORT,
    }
)

CORE_CONCEPT = "concept"
CORE_ENTITY = "entity"
CORE_PERIOD = "period"
CORE_UNIT = "unit"
CORE_LANGUAGE = "language"
CORE_DECIMALS = "decimals"

_CORE_EFFECTIVE_LEXICAL_TYPES: Mapping[str, QName] = MappingProxyType(
    {
        CORE_CONCEPT: QNAME,
        CORE_ENTITY: TOKEN,
        CORE_PERIOD: STRING,
        CORE_UNIT: STRING,
        CORE_LANGUAGE: STRING,
        CORE_DECIMALS: INTEGER,
    }
)


OPTIONALLY_TIME_ZONED_TYPES = frozenset(
    {
        DATE,
        DATE_TIME,
        TIME,
        G_YEAR,
        G_YEAR_MONTH,
        G_MONTH_DAY,
        G_MONTH,
        G_DAY,
    }
)

PROHIBITED_KEY_TYPES = frozenset(
    {
        DOUBLE,
        FLOAT,
        HEX_BINARY,
        BASE64_BINARY,
        LANGUAGE,
    }
)


def resolve_effective_lexical_type(constraint_type: str, namespaces: Mapping[str, str]) -> QName | None:
    if core_effective_type := _CORE_EFFECTIVE_LEXICAL_TYPES.get(constraint_type):
        return core_effective_type
    prefix, _, local_name = constraint_type.partition(":")
    if namespace_uri := namespaces.get(prefix):
        effective_type = QName(prefix, namespace_uri, local_name)
        if effective_type in _TC_PERMITTED_SCHEMA_TYPES:
            return effective_type
    return None
