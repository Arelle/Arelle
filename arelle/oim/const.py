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

PER_ISO_PATTERN = regex.compile(
    "([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-2][0-9]([:]?)[0-5][0-9]+)?(/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})?(Z|[+-][0-2][0-9]([:]?)[0-5][0-9]+)?)$"
)
PER_INCLUSIVE_DATES_PATTERN = regex.compile("([0-9]{4}-[0-9]{2}-[0-9]{2})[.][.]([0-9]{4}-[0-9]{2}-[0-9]{2})$")
PER_SINGLE_DAY_PATTERN = regex.compile("([0-9]{4}-[0-9]{2}-[0-9]{2})(@(start|end))?$")
PER_MONTH_PATTERN = regex.compile("([0-9]{4}-[0-9]{2})(@(start|end))?$")
PER_YEAR_PATTERN = regex.compile("([0-9]{4})(@(start|end))?$")
PER_QTR_PATTERN = regex.compile("([0-9]{4})Q([1-4])(@(start|end))?$")
PER_HALF_PATTERN = regex.compile("([0-9]{4})H([1-2])(@(start|end))?$")
PER_WEEK_PATTERN = regex.compile("([0-9]{4}W[1-5]?[0-9])(@(start|end))?$")
