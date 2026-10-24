"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle import XbrlConst
from arelle.ModelValue import QName, qname

# Arelle starts these codes with a reference to the rule that reports them, which suites leave out or qualify differently.
RULE_REFERENCED_CODE_PREFIXES = ("ESEF.", "NL.NL-KVK")


def error_code_matches(expected: Any, actual: Any) -> bool:
    """
    Whether an error code (or assertion result) reported by Arelle satisfies one listed by a conformance suite.
    """
    if isinstance(expected, dict) or isinstance(actual, dict):
        return isinstance(expected, dict) and isinstance(actual, dict) and _formula_assertion_counts_match(expected, actual)
    if not isinstance(actual, str) or not isinstance(expected, (QName, str)):
        return bool(actual == expected)
    matched = False
    if isinstance(expected, QName):
        if actual.startswith("{"):
            return bool(qname(actual) == expected)
        prefix, sep, local_name = actual.rpartition(":")
        if (
                # An unprefixed suite QName is only in the testcase's default namespace, so its text is the code.
                (not sep and _same_literal(str(expected), actual)) or
                (expected == qname(XbrlConst.errMsgPrefixNS.get(prefix) or
                           (prefix == expected.prefix and expected.namespaceURI),
                           local_name)) or
                # XDT xml schema tests expected results
                (expected.namespaceURI == XbrlConst.xdtSchemaErrorNS and prefix == "xmlSchema") or
                # UKSEF conformance suite expects XML schema validation errors in format xbrl.core.xml.SchemaValidationError.*
                # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
                (expected.localName.startswith("xbrl.core.xml.SchemaValidationError.cvc") and prefix == "xmlSchema")
        ):
            matched = True
    elif (actual == expected or
             _same_literal(expected, actual) or
             (expected == "html:syntaxError" and actual.startswith("lxml.SCHEMA")) or
             (expected == "EFM.6.03.04" and actual.startswith("xmlSchema:")) or
             (expected == "EFM.6.03.05" and (actual.startswith("xmlSchema:") or actual == "EFM.5.02.01.01")) or
             (expected == "EFM.6.04.03" and (actual.startswith("xmlSchema:") or actual.startswith("utr:") or actual.startswith("xbrl.") or actual.startswith("xlink:"))) or
             (expected == "EFM.6.05.35" and actual.startswith("utre:")) or
             (expected.startswith("EFM.") and actual.startswith(expected)) or
             (expected.startswith("EXG.") and actual.startswith(expected)) or
             (expected == "vere:invalidDTSIdentifier" and actual.startswith("xbrl"))
             ):
        matched = True
    return matched


def _formula_assertion_counts_match(expected: dict[str, tuple[int, int]], actual: dict[str, tuple[int, ...]]) -> bool:
    # Arelle reports ok, warning and error message counts after the satisfied and not satisfied counts suites list.
    return {assertion_id: counts[:2] for assertion_id, counts in actual.items()} == expected


def _same_literal(expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    if not actual.startswith(RULE_REFERENCED_CODE_PREFIXES):
        return False
    # Suites may qualify the name differently, such as xbrl.efr.esef.uk.name for ESEF.UKFRC1.name.
    actual_name = actual.rpartition(".")[2]
    expected_name = expected.rpartition(".")[2]
    # A numeric final segment is part of a rule number, not a name.
    if actual_name.isdigit():
        return False
    return actual_name == expected_name
