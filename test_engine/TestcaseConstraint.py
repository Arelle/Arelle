"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import cached_property

from arelle import XbrlConst
from arelle.ModelValue import QName


@dataclass(frozen=True)
class TestcaseConstraint:
    qname: QName | None
    pattern: str | None
    min: int | None
    max: int | None
    warnings: bool
    errors: bool

    def __str__(self):
        value = str(self.qname or self.pattern or '(any)')
        if self.errors:
            value += " [E]"
        if self.warnings:
            value += " [W]"
        minCount = self.min or 1
        maxCount = self.max or 1
        if minCount == maxCount:
            value += f" ={minCount}"
        else:
            if self.min is not None:
                value += f" >={self.min}"
            if self.max is not None:
                value += f" <={self.max}"
        return value

    def compareCode(self, code: str) -> bool:
        if code is None:
            return False
        if self.qname is not None:
            if str(self.qname) == code:
                return True
            if self.qname.localName == code:
                return True
            if self.qname.localName == code.split('.')[-1]:
                return True
        if self.pattern is not None:
            if self.pattern in code:
                return True
        prefix, sep, localName = code.partition(':')
        namespaceUri = XbrlConst.errMsgPrefixNS.get(prefix)
        qname = QName(prefix, namespaceUri, localName)
        return self.compareQname(qname)

    def compareQname(self, qname: QName) -> bool:
        if self.qname is None or qname is None:
            return False
        if self.qname == qname:
            return True
        return False
