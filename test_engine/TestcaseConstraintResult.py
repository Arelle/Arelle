from dataclasses import dataclass

from arelle.ModelValue import QName


@dataclass(frozen=True)
class TestcaseConstraintResult:
    code: str | QName
    diff: int

    def __str__(self):
        num = str(self.diff)
        if self.diff > 0:
            num = f'+{num}'
        return f"{num:>10} \t\"{self.code}\""
