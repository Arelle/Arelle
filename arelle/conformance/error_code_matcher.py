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

# Suite codes that Arelle reports as a different code, mapped to the codes that satisfy them.
SUITE_CODE_ALTERNATIVES: dict[str, frozenset[str]] = {
    # EFM suites expect an HTML syntax error where Arelle reports XHTML schema validation errors.
    "html:syntaxError": frozenset({"lxml.SCHEMAV_CVC_COMPLEX_TYPE_3_2_1", "lxml.SCHEMAV_ELEMENT_CONTENT"}),
    # EFM rules that Arelle reports as the underlying schema, unit registry, or document character error.
    "EFM.6.03.04": frozenset({"xmlSchema:syntax"}),
    "EFM.6.03.05": frozenset({"xmlSchema:syntax", "EFM.5.02.01.01"}),
    "EFM.6.04.03": frozenset({"xmlSchema:valueError"}),
    "EFM.6.05.35": frozenset({"utre:error-NumericFactUtrInvalid"}),
    # UKSEF names schema errors after the constraint they violate.
    # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
    "xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a": frozenset({"xmlSchema:elementUnexpected"}),
}


def error_code_matches(expected: Any, actual: Any) -> bool:
    """
    Whether an error code (or assertion result) reported by Arelle satisfies one listed by a conformance suite.
    """
    if isinstance(expected, dict) or isinstance(actual, dict):
        return isinstance(expected, dict) and isinstance(actual, dict) and _formula_assertion_counts_match(expected, actual)
    if not isinstance(actual, str) or not isinstance(expected, (QName, str)):
        return bool(actual == expected)
    if actual in SUITE_CODE_ALTERNATIVES.get(str(expected), ()):
        return True
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
                (expected.namespaceURI == XbrlConst.xdtSchemaErrorNS and prefix == "xmlSchema")
        ):
            matched = True
    elif _same_literal(expected, actual):
        matched = True
    return matched


def _formula_assertion_counts_match(expected: dict[str, tuple[int, int]], actual: dict[str, tuple[int, ...]]) -> bool:
    # Arelle reports ok, warning and error message counts after the satisfied and not satisfied counts suites list.
    return {assertion_id: counts[:2] for assertion_id, counts in actual.items()} == expected


def _same_literal(expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    if expected.startswith(HIERARCHICAL_CODE_PREFIXES) and actual.startswith(expected + "."):
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
