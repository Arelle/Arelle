from dataclasses import dataclass

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
        value = str(self.qname or self.pattern)
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
