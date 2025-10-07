from dataclasses import dataclass

from test_suite.ActualError import ActualError
from test_suite.TestcaseConstraintResult import TestcaseConstraintResult
from test_suite.TestcaseVariation import TestcaseVariation


@dataclass(frozen=True)
class TestcaseResult:
    testcaseVariation: TestcaseVariation
    actualErrors: list[ActualError]
    constraintResults: list[TestcaseConstraintResult]
    passed: bool
    skip: bool # TODO
    duration_seconds: float

    def __str__(self):
        return (
            (f"{self.testcaseVariation.shortName} \t") +
            ("PASS " if self.passed else "FAIL ") +
            (", ".join(str(r) for r in self.constraintResults))
        ).strip()

    @property
    def status(self) -> str:
        if self.skip:
            return "skip"
        return "pass" if self.passed else "fail"
