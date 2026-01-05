"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

from arelle.ModelValue import QName
from test_engine.ErrorLevel import ErrorLevel


@dataclass(frozen=True)
class TestcaseConstraint:
    qname: QName | None = None
    pattern: str | None = None
    min: int | None = None
    max: int | None = None
    level: ErrorLevel = ErrorLevel.ERROR

    def __str__(self) -> str:
        value = str(self.qname or self.pattern or '(any)')
        if self.level:
            value += f" [{self.level}]"
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
