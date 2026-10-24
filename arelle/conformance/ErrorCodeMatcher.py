"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle import XbrlConst
from arelle.ModelValue import QName, qname

# Arelle starts these codes with a reference to the rule that reports them, which suites leave out or qualify differently.
RULE_REFERENCED_CODE_PREFIXES = ("ESEF.", "NL.NL-KVK")

# Hierarchical codes where Arelle reports a more specific code below the one a suite expects.
HIERARCHICAL_CODE_PREFIXES = ("EFM.", "EXG.")


def errorCodeMatches(expected: Any, actual: Any) -> bool:
    """
    Whether an error code (or assertion result) reported by Arelle satisfies one listed by a conformance suite.
    """
    matched = False
    if isinstance(expected,QName) and isinstance(actual,str):
        if actual.startswith("{"):
            return bool(qname(actual) == expected)
        prefix, sep, localName = actual.rpartition(":")
        if (
                # An unprefixed suite QName is only in the testcase's default namespace, so its text is the code.
                (not sep and _sameLiteral(str(expected), actual)) or
                (expected == qname(XbrlConst.errMsgPrefixNS.get(prefix) or
                           (prefix == expected.prefix and expected.namespaceURI),
                           localName)) or
                # XDT xml schema tests expected results
                (expected.namespaceURI == XbrlConst.xdtSchemaErrorNS and prefix == "xmlSchema") or
                # UKSEF conformance suite expects XML schema validation errors in format xbrl.core.xml.SchemaValidationError.*
                # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
                (expected.localName.startswith("xbrl.core.xml.SchemaValidationError.cvc") and prefix == "xmlSchema")
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
             _sameLiteral(expected, actual) or
             (expected == "html:syntaxError" and actual.startswith("lxml.SCHEMA")) or
             (expected == "EFM.6.03.04" and actual.startswith("xmlSchema:")) or
             (expected == "EFM.6.03.05" and (actual.startswith("xmlSchema:") or actual == "EFM.5.02.01.01")) or
             (expected == "EFM.6.04.03" and (actual.startswith("xmlSchema:") or actual.startswith("utr:") or actual.startswith("xbrl.") or actual.startswith("xlink:"))) or
             (expected == "EFM.6.05.35" and actual.startswith("utre:")) or
             (expected == "vere:invalidDTSIdentifier" and actual.startswith("xbrl"))
             ))):
            matched = True
    return matched


def _sameLiteral(expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    if expected.startswith(HIERARCHICAL_CODE_PREFIXES) and actual.startswith(expected + "."):
        return True
    # Suites may qualify the name differently, such as xbrl.efr.esef.uk.name for ESEF.UKFRC1.name.
    return actual.startswith(RULE_REFERENCED_CODE_PREFIXES) and actual.rpartition(".")[2] == expected.rpartition(".")[2]
