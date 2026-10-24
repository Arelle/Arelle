"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

import regex as re

from arelle import XbrlConst
from arelle.ModelValue import QName, qname

COMMA_SPACE_SPLIT_PATTERN = re.compile(r",\s*")


def error_code_matches(expected: Any, actual: Any) -> bool:
    """
    Whether an error code (or assertion result) reported by Arelle satisfies one listed by a conformance suite.
    """
    actual_prefix = None
    if isinstance(actual, str) and actual.startswith(("ESEF.", "NL.NL-KVK")): # compared as list of strings to QName localname
        actual_prefix, __, actual_suffix = actual.rpartition(".")
        if not actual_suffix.isdigit():
            actual = actual_suffix
    matched = False
    if isinstance(expected,QName) and isinstance(actual,str):
        prefix, sep, local_name = actual.rpartition(":")
        if (
                # ESEF has comma separated list of localnames of errors
                (not sep and local_name in COMMA_SPACE_SPLIT_PATTERN.split(expected.localName.strip())) or
                (expected == qname(XbrlConst.errMsgPrefixNS.get(prefix) or
                           (prefix == expected.prefix and expected.namespaceURI),
                           local_name)) or
                # XDT xml schema tests expected results
                (expected.namespaceURI == XbrlConst.xdtSchemaErrorNS and prefix == "xmlSchema") or
                # UKSEF conformance suite expects XML schema validation errors in format xbrl.core.xml.SchemaValidationError.*
                # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
                (expected.localName.startswith("xbrl.core.xml.SchemaValidationError.cvc") and prefix == "xmlSchema") or
                # ESEF.UK*: Actual (str): *:match, Expected (QName): {*}*.match
                (
                        actual_prefix and actual_prefix.startswith("ESEF.UK") and
                        local_name and local_name == expected.localName.rpartition(".")[2]
                )
        ):
            matched = True
    elif type(actual) is type(expected):
        if isinstance(actual,dict):
            if len(actual) == len(expected) and all(
                k in actual and counts == actual[k][:len(counts)]
                for k, counts in expected.items()):
                matched = True
        elif (actual == expected or
            (isinstance(expected, str) and (
             (expected == "html:syntaxError" and actual.startswith("lxml.SCHEMA")) or
             (expected == "EFM.6.03.04" and actual.startswith("xmlSchema:")) or
             (expected == "EFM.6.03.05" and (actual.startswith("xmlSchema:") or actual == "EFM.5.02.01.01")) or
             (expected == "EFM.6.04.03" and (actual.startswith("xmlSchema:") or actual.startswith("utr:") or actual.startswith("xbrl.") or actual.startswith("xlink:"))) or
             (expected == "EFM.6.05.35" and actual.startswith("utre:")) or
             (expected.startswith("EFM.") and actual.startswith(expected)) or
             (expected.startswith("EXG.") and actual.startswith(expected)) or
             (expected == "vere:invalidDTSIdentifier" and actual.startswith("xbrl"))
             ))):
            matched = True
    return matched
