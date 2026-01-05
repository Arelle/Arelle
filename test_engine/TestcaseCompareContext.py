"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from arelle.ModelValue import QName
from test_engine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestcaseCompareContext:
    customComparePatterns: list[tuple[str, str]] = field(default_factory=list)
    localNameMap: dict[str | None, dict[str, str]] = field(default_factory=dict)
    prefixNamespaceUriMap: dict[str | None, str] = field(default_factory=dict)

    @staticmethod
    def _compareCode(testcaseConstraint: TestcaseConstraint, code: str) -> bool:
        if testcaseConstraint.qname is not None:
            if str(testcaseConstraint.qname) == code:
                return True
            if testcaseConstraint.qname.localName == code:
                return True
            if testcaseConstraint.qname.localName == code.split('.')[-1]:
                return True
        if testcaseConstraint.pattern is not None:
            if testcaseConstraint.pattern in code:
                return True
        return False

    @staticmethod
    def _compareQname(testcaseConstraint: TestcaseConstraint, qname: QName) -> bool:
        if testcaseConstraint.qname is None or qname is None:
            return False
        if testcaseConstraint.qname == qname:
            return True
        return False

    def _compareCustomPatterns(self, expected: str, actual: str) -> bool:
        mapping = [
            (r"^EFM\.6\.03\.04$", r"^xmlSchema:.*$"),
            (r"^EFM\.6\.03\.05$", r"^(xmlSchema:.*|EFM\.5\.02\.01\.01)$"),
            (r"^EFM\.6\.04\.03$", r"^(xmlSchema:.*|utr:.*|xbrl\..*|xlink:.*)$"),
            (r"^EFM\.6\.05\.35$", r"^utre:.*$"),
            (r"^html:syntaxError$", r"^lxml\.SCHEMA.*$"),
            (r"^vere:invalidDTSIdentifier$", r"^xbrl.*$"),
            # Generic prefix matches for the 'expected' side
            (r"^EFM\..*$", r"^~.*$"),
            (r"^EXG\..*$", r"^~.*$"),
        ]

        for expectedPattern, actualPattern in self.customComparePatterns:
            if re.fullmatch(expectedPattern, expected):
                actualPattern = actualPattern.replace('~', expected)
                if re.fullmatch(actualPattern, actual):
                    return True
        return False

    def compare(self, testcaseConstraint: TestcaseConstraint, actualError: QName | str) -> bool:
        if isinstance(actualError, QName):
            return TestcaseCompareContext._compareQname(testcaseConstraint, actualError)
        if TestcaseCompareContext._compareCode(testcaseConstraint, actualError):
            return True
        qname = self.mapToQName(actualError)
        if self._compareQname(testcaseConstraint, qname):
            return True
        return self._compareCustomPatterns(testcaseConstraint.pattern or str(testcaseConstraint.qname), actualError)

    def mapToQName(self, actualError: str) -> QName:
        prefix, sep, localName = actualError.rpartition(':')
        namespaceUri = self.prefixNamespaceUriMap.get(prefix)
        localName = self.localNameMap.get(namespaceUri, {}).get(localName, localName)
        return QName(prefix, namespaceUri, localName)

# QName
    # self.qname is None -> False
    # qname is None -> False
    # self.qname = qname -> True
    # self.qname != qname -> False

# str
    # self.qname is not None
        # str(self.qname) == code -> True
        # self.qname.localName == code -> True
        # self.qname.localName == code.split('.')[-1] -> True
    # self.pattern is not None
        # self.pattern in code -> True ########
    # parse QName
        # self.qname is None -> False
        # qname is None -> False
        # self.qname = qname -> True
        # self.qname = qname (mapped namespace URI, no localname) -> True
        # self.qname = qname (mapped namespace URI, mapped localname) -> True
        # self.qname != qname -> False
    # Custom patterns ####

    # No match ########
