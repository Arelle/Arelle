"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle import XbrlConst
from arelle.ModelValue import QName, qname

# Arelle starts these codes with a reference to the rule that reports them, which suites leave out or qualify differently.
RULE_REFERENCED_CODE_PREFIXES = ("ESEF.", "NL.NL-KVK")


def errorCodeMatches(_exp: Any, testErr: Any) -> bool:
    """
    Whether an error code (or assertion result) reported by Arelle satisfies one listed by a conformance suite.
    """
    _expMatched = False
    if isinstance(_exp,QName) and isinstance(testErr,str):
        if testErr.startswith("{"):
            return bool(qname(testErr) == _exp)
        errPrefix, sep, errLocalName = testErr.rpartition(":")
        if (
                # An unprefixed suite QName is only in the testcase's default namespace, so its text is the code.
                (not sep and _sameLiteral(str(_exp), testErr)) or
                (_exp == qname(XbrlConst.errMsgPrefixNS.get(errPrefix) or
                           (errPrefix == _exp.prefix and _exp.namespaceURI),
                           errLocalName)) or
                # XDT xml schema tests expected results
                (_exp.namespaceURI == XbrlConst.xdtSchemaErrorNS and errPrefix == "xmlSchema") or
                # UKSEF conformance suite expects XML schema validation errors in format xbrl.core.xml.SchemaValidationError.*
                # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
                (_exp.localName.startswith("xbrl.core.xml.SchemaValidationError.cvc") and errPrefix == "xmlSchema")
        ):
            _expMatched = True
    elif type(testErr) is type(_exp):
        if isinstance(testErr,dict):
            if len(testErr) == len(_exp) and all(
                k in testErr and counts == testErr[k][:len(counts)]
                for k, counts in _exp.items()):
                _expMatched = True
        elif (testErr == _exp or
            (isinstance(_exp, str) and (
             _sameLiteral(_exp, testErr) or
             (_exp == "html:syntaxError" and testErr.startswith("lxml.SCHEMA")) or
             (_exp == "EFM.6.03.04" and testErr.startswith("xmlSchema:")) or
             (_exp == "EFM.6.03.05" and (testErr.startswith("xmlSchema:") or testErr == "EFM.5.02.01.01")) or
             (_exp == "EFM.6.04.03" and (testErr.startswith("xmlSchema:") or testErr.startswith("utr:") or testErr.startswith("xbrl.") or testErr.startswith("xlink:"))) or
             (_exp == "EFM.6.05.35" and testErr.startswith("utre:")) or
             (_exp.startswith("EFM.") and testErr.startswith(_exp)) or
             (_exp.startswith("EXG.") and testErr.startswith(_exp)) or
             (_exp == "vere:invalidDTSIdentifier" and testErr.startswith("xbrl"))
             ))):
            _expMatched = True
    return _expMatched


def _sameLiteral(expected: str, actual: str) -> bool:
    if actual == expected:
        return True
    # Suites may qualify the name differently, such as xbrl.efr.esef.uk.name for ESEF.UKFRC1.name.
    return actual.startswith(RULE_REFERENCED_CODE_PREFIXES) and actual.rpartition(".")[2] == expected.rpartition(".")[2]
