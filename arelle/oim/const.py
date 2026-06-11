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
    "[_A-Za-z\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd]"
    r"[_\-\."
    "\xb7A-Za-z0-9\xc0-\xd6\xd8-\xf6\xf8-\xff\u0100-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\u0300-\u036f\u203f-\u2040]*:"
    r"\S+"
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
