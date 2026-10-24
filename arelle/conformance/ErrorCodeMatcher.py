"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

import regex as re

from arelle import XbrlConst
from arelle.ModelValue import QName, qname

commaSpaceSplitPattern = re.compile(r",\s*")


def errorCodeMatches(_exp: Any, testErr: Any) -> bool:
    """
    Whether an error code (or assertion result) reported by Arelle satisfies one listed by a conformance suite.
    """
    testErrPrefix = None
    if isinstance(testErr, str) and testErr.startswith(("ESEF.", "NL.NL-KVK")): # compared as list of strings to QName localname
        testErrPrefix, __, testErrSuffix = testErr.rpartition(".")
        if not testErrSuffix.isdigit():
            testErr = testErrSuffix
    _expMatched = False
    if isinstance(_exp,QName) and isinstance(testErr,str):
        if testErr.startswith("{"):
            return bool(qname(testErr) == _exp)
        errPrefix, sep, errLocalName = testErr.rpartition(":")
        if (
                # ESEF has comma separated list of localnames of errors
                (not sep and errLocalName in commaSpaceSplitPattern.split(_exp.localName.strip())) or
                (_exp == qname(XbrlConst.errMsgPrefixNS.get(errPrefix) or
                           (errPrefix == _exp.prefix and _exp.namespaceURI),
                           errLocalName)) or
                # XDT xml schema tests expected results
                (_exp.namespaceURI == XbrlConst.xdtSchemaErrorNS and errPrefix == "xmlSchema") or
                # UKSEF conformance suite expects XML schema validation errors in format xbrl.core.xml.SchemaValidationError.*
                # Example: tests/FRC/FRC_08/index.xml:TC2_invalid
                (_exp.localName.startswith("xbrl.core.xml.SchemaValidationError.cvc") and errPrefix == "xmlSchema") or
                # ESEF.UK*: Actual (str): *:match, Expected (QName): {*}*.match
                (
                        testErrPrefix and testErrPrefix.startswith("ESEF.UK") and
                        errLocalName and errLocalName == _exp.localName.rpartition(".")[2]
                )
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
