"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, TypeVar

from arelle import XbrlConst
from arelle.ModelValue import QName, qname

ErrorT = TypeVar("ErrorT")

# Arelle starts these codes with a reference to the rule that reports them, which suites leave out or qualify differently.
RULE_REFERENCED_CODE_PREFIXES = ("ESEF.", "NL.NL-KVK")

# The UKSEF suite qualifies its codes with the authority whose rule reports them, and uses some names for both.
UKSEF_SUITE_CODE_AUTHORITIES = {"xbrl.efr.esef.esma.": "esma", "xbrl.efr.esef.uk.": "uk"}
# Arelle reports ESMA rules without the ESEF.UK prefix, and these UK rules reuse a name the suite also gives the other
# authority. Other UK rules have names only one authority uses, so their codes match either qualification.
UKSEF_RULE_AUTHORITIES = {"ESEF.UKFRC6": "esma", "ESEF.UKFRC7": "uk", "ESEF.UKFRC18": "uk"}

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
    # UKSEF names schema errors after the constraint they violate, and libxml2 numbers some clauses differently.
    # Examples: tests/FRC/FRC_08/index.xml:TC2_invalid and the ignored errors of tests/FRC/FRC_20/index.xml:TC3_invalid
    "xbrl.core.xml.SchemaValidationError.cvc-complex-type_2_4_a": frozenset({"xmlSchema:elementUnexpected"}),
    "xbrl.core.xml.SchemaValidationError.cvc-complex-type_3_2_2": frozenset({"lxml.SCHEMAV_CVC_COMPLEX_TYPE_3_2_1"}),
    "xbrl.core.xml.SchemaValidationError.cvc-complex-type_4": frozenset({"lxml.SCHEMAV_CVC_COMPLEX_TYPE_4"}),
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
    return _same_code(expected, actual)


def filter_ignored_errors(errors: list[ErrorT], ignored_codes: Sequence[QName | str], suite_expected_codes: Sequence[QName | str]) -> list[ErrorT]:
    """
    Remove errors matching a code the conformance suite ignores, unless they also match a code the suite itself expects.
    Some variations ignore a code they also expect.
    """
    return [
        error for error in errors
        if not any(error_code_matches(ignored_code, error) for ignored_code in ignored_codes)
        or any(error_code_matches(expected_code, error) for expected_code in suite_expected_codes)
    ]


def _formula_assertion_counts_match(expected: dict[str, tuple[int, int]], actual: dict[str, tuple[int, ...]]) -> bool:
    # Arelle reports ok, warning and error message counts after the satisfied and not satisfied counts suites list.
    return {assertion_id: counts[:2] for assertion_id, counts in actual.items()} == expected


def _same_code(expected: QName | str, actual: str) -> bool:
    if isinstance(expected, QName):
        if actual.startswith("{"):
            return bool(qname(actual) == expected)
        prefix, sep, local_name = actual.rpartition(":")
        if sep:
            return _resolves_to(expected, prefix, local_name)
    # Arelle codes without a namespace can only be compared as text. The text of a suite QName without a prefix is
    # its local name, since the testcase's default namespace isn't an error namespace.
    return _same_literal(str(expected), actual)


def _resolves_to(expected: QName, prefix: str, local_name: str) -> bool:
    # Arelle's prefixes aren't declared, so one the suite also uses is taken to mean the same namespace.
    namespace_uri = XbrlConst.errMsgPrefixNS.get(prefix) or (expected.namespaceURI if prefix == expected.prefix else None)
    if not namespace_uri or namespace_uri != expected.namespaceURI:
        return False
    # The generic schema error namespace stands for any XML schema error.
    if namespace_uri == XbrlConst.xdtSchemaErrorNS:
        return True
    return local_name == expected.localName


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
    if _different_uksef_authorities(expected, actual):
        return False
    return actual_name == expected_name


def _different_uksef_authorities(expected: str, actual: str) -> bool:
    expected_authority = next(
        (authority for prefix, authority in UKSEF_SUITE_CODE_AUTHORITIES.items() if expected.startswith(prefix)), None
    )
    if expected_authority is None:
        return False
    if not actual.startswith("ESEF.UK"):
        return expected_authority != "esma"
    actual_authority = UKSEF_RULE_AUTHORITIES.get(actual.rpartition(".")[0])
    return actual_authority is not None and actual_authority != expected_authority
