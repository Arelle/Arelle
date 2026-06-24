"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import regex

IDENTIFIER_PATTERN = regex.compile(
    "^[_A-Za-z\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd]"
    r"[_\-"
    "\xb7A-Za-z0-9\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\u0300-\u036f\u203f-\u2040]*$"
)

PREFIXED_QNAME_PATTERN = regex.compile(
    "[_A-Za-z\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd]"
    r"[_\-\."
    "\xb7A-Za-z0-9\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\u0300-\u036f\u203f-\u2040]*:"
    "[_A-Za-z\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd]"
    r"[_\-\."
    "\xb7A-Za-z0-9\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\u0300-\u036f\u203f-\u2040]*"
)

SQNAME_PATTERN = regex.compile(
    r"(?P<prefix>"
    "[_A-Za-z\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd]"
    r"[_\-\."
    "\xb7A-Za-z0-9\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\u0300-\u036f\u203f-\u2040]*"
    r")"
    r":"
    r"(?P<localName>\S+)"
)

UNIT_QNAME_SUBSTITUTION_CHAR = "\x07"  # replaces PrefixedQName in unit pattern

UNIT_PATTERN = regex.compile(
    # QNames are replaced by \x07 in these expressions
    # numerator only (no parentheses)
    "(^\x07$)|(^\x07([*]\x07)+$)|"
    # numerator and optional denominator, with parentheses if more than one term in either
    "(^((\x07)|([(]\x07([*]\x07)+[)]))([/]((\x07)|([(]\x07([*]\x07)+[)])))?$)"
)

XBRLCE_INVALID_IDENTIFIER = "xbrlce:invalidIdentifier"

_YEAR = r"[0-9]{4}"
_DATE = rf"{_YEAR}-[0-9]{{2}}-[0-9]{{2}}"
_TIME = r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
# OIM periods require canonical UTC (Z), so +00:00/-00:00 are rejected.
_PER_TZ = r"(?:Z|[+-](?!00:?00)[0-2][0-9]:?[0-5][0-9])"
_PER_DATETIME = rf"{_DATE}T{_TIME}(?:{_PER_TZ})?"
_SUFFIX = r"@(?P<suffix>start|end)"

PER_TZ_PATTERN = regex.compile(rf"(?:{_PER_TZ})$")
PER_ISO_PATTERN = regex.compile(rf"(?P<start>{_PER_DATETIME})(?:/(?P<end>{_PER_DATETIME}))?$")
PER_INCLUSIVE_DATES_PATTERN = regex.compile(rf"(?P<start>{_DATE})\.\.(?P<end>{_DATE})$")
PER_SINGLE_DAY_PATTERN = regex.compile(rf"(?P<date>{_DATE})(?:{_SUFFIX})?$")
PER_MONTH_PATTERN = regex.compile(rf"(?P<year>{_YEAR})-(?P<month>[0-9]{{2}})(?:{_SUFFIX})?$")
PER_YEAR_PATTERN = regex.compile(rf"(?P<year>{_YEAR})(?:{_SUFFIX})?$")
PER_QTR_PATTERN = regex.compile(rf"(?P<year>{_YEAR})Q(?P<quarter>[1-4])(?:{_SUFFIX})?$")
PER_HALF_PATTERN = regex.compile(rf"(?P<year>{_YEAR})H(?P<half>[12])(?:{_SUFFIX})?$")
PER_WEEK_PATTERN = regex.compile(rf"(?P<year>{_YEAR})W(?P<week>[0-9]{{2}})(?:{_SUFFIX})?$")
