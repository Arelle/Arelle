from dataclasses import dataclass

from arelle.ModelValue import QName


@dataclass(frozen=True)
class TestcaseConstraintResult:
    code: str | QName
    diff: int

    def __str__(self):
        descriptor = ""
        if self.diff > 0:
            descriptor = "extra"
        elif self.diff < 0:
            descriptor = "missing"
        return f"({self.diff}) \"{self.code}\" {descriptor}"
