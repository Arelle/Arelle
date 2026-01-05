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
        if testcaseConstraint.pattern is not None:
            if testcaseConstraint.pattern == code:
                return True
        return False

    @staticmethod
    def _compareQname(testcaseConstraint: TestcaseConstraint, qname: QName) -> bool:
        if qname is None:
            return False
        if testcaseConstraint.qname is None:
            if testcaseConstraint.pattern == qname.localName:
                return True
        if testcaseConstraint.qname == qname:
            return True
        return False

    def _compareCustomPatterns(self, expected: str, actual: str) -> bool:
        for expectedPattern, actualPattern in self.customComparePatterns:
            if re.fullmatch(expectedPattern, expected):
                actualPattern = actualPattern.replace('~', expected)
                if re.fullmatch(actualPattern, actual):
                    return True
        return False

    def compare(self, testcaseConstraint: TestcaseConstraint, actualError: str) -> bool:
        if testcaseConstraint.pattern == "*":
            return True
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
