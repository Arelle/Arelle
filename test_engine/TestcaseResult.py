from dataclasses import dataclass

from test_engine.ActualError import ActualError
from test_engine.TestcaseConstraintResult import TestcaseConstraintResult
from test_engine.TestcaseConstraintSet import TestcaseConstraintSet
from test_engine.TestcaseVariation import TestcaseVariation


@dataclass(frozen=True)
class TestcaseResult:
    testcaseVariation: TestcaseVariation
    appliedConstraintSet: TestcaseConstraintSet
    actualErrors: list[ActualError]
    constraintResults: list[TestcaseConstraintResult]
    passed: bool
    skip: bool # TODO
    duration_seconds: float
    blockedErrors: dict[str, int]

    def __str__(self):
        return (
            (f"{self.testcaseVariation.shortName} \t") +
            (self.status.upper()) +
            (", ".join(str(r) for r in self.constraintResults))
        ).strip()

    def report(self) -> str:
        return (
            f"[{self}]\n"
            f"\tID: {self.testcaseVariation.fullId}\n"
            f"\tStatus: {self.status.upper()}\n"
            f"\tDuration: {self.duration_seconds:.2f} seconds\n"
            f"\tExpected:\n" +
            ("\n".join(f"\t\t {e}" for e in self.appliedConstraintSet.constraints) if self.appliedConstraintSet.constraints else "\t\t None") + "\n"
            f"\tActual:\n" +
            ("\n".join(f"\t\t {e.qname or e.code or e.assertions}" for e in self.actualErrors) if self.actualErrors else "\t\t None") + "\n"
            f"\tBlocked:\n" +
            ("\n".join(f"\t\t {e}: {c}" for e, c in self.blockedErrors.items()) if self.blockedErrors else "\t\t None") + "\n"
            f"\tResults:\n" +
            ("\n".join(f"\t\t {r}" for r in self.constraintResults) if self.constraintResults else "\t\t None")
        )

    @property
    def status(self) -> str:
        if self.skip:
            return "skip"
        return "pass" if self.passed else "fail"
