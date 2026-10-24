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
    if isinstance(expected, dict) or isinstance(actual, dict):
        return isinstance(expected, dict) and isinstance(actual, dict) and _assertionCountsMatch(expected, actual)
    if not isinstance(actual, str) or not isinstance(expected, (QName, str)):
        return bool(actual == expected)
    return _sameCode(expected, actual) or _satisfiesBroaderCode(expected, actual)


def _assertionCountsMatch(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return len(actual) == len(expected) and all(
        assertionId in actual and counts == actual[assertionId][:len(counts)]
        for assertionId, counts in expected.items()
    )


def _sameCode(expected: QName | str, actual: str) -> bool:
    if actual.startswith("{") and isinstance(expected, QName):
        return bool(qname(actual) == expected)
    prefix, sep, localName = actual.rpartition(":")
    if sep and isinstance(expected, QName):
        return _resolvesTo(expected, prefix, localName)
    # An unprefixed suite QName is only in the testcase's default namespace, so its text is the code.
    return _sameLiteral(str(expected), actual)


def _resolvesTo(expected: QName, prefix: str, localName: str) -> bool:
    # Arelle's prefixes aren't declared, so one the suite also uses is taken to mean the same namespace.
    namespaceURI = XbrlConst.errMsgPrefixNS.get(prefix) or (expected.namespaceURI if prefix == expected.prefix else None)
    return bool(namespaceURI) and namespaceURI == expected.namespaceURI and localName == expected.localName


def _sameLiteral(expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    if expected.startswith(HIERARCHICAL_CODE_PREFIXES) and actual.startswith(expected + "."):
        return True
    # Suites may qualify the name differently, such as xbrl.efr.esef.uk.name for ESEF.UKFRC1.name.
    return actual.startswith(RULE_REFERENCED_CODE_PREFIXES) and actual.rpartition(".")[2] == expected.rpartition(".")[2]


def _satisfiesBroaderCode(expected: QName | str, actual: str) -> bool:
    if isinstance(expected, QName):
        return actual.rpartition(":")[0] == "xmlSchema" and (
            # XDT xml schema tests expected results
            expected.namespaceURI == XbrlConst.xdtSchemaErrorNS or
            # UKSEF conformance suite expects XML schema validation errors in format xbrl.core.xml.SchemaValidationError.*
            # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
            expected.localName.startswith("xbrl.core.xml.SchemaValidationError.cvc")
        )
    return (
        (expected == "html:syntaxError" and actual.startswith("lxml.SCHEMA")) or
        (expected == "EFM.6.03.04" and actual.startswith("xmlSchema:")) or
        (expected == "EFM.6.03.05" and (actual.startswith("xmlSchema:") or actual == "EFM.5.02.01.01")) or
        (expected == "EFM.6.04.03" and (actual.startswith("xmlSchema:") or actual.startswith("utr:") or actual.startswith("xbrl.") or actual.startswith("xlink:"))) or
        (expected == "EFM.6.05.35" and actual.startswith("utre:")) or
        (expected == "vere:invalidDTSIdentifier" and actual.startswith("xbrl"))
    )
