from dataclasses import dataclass

from test_suite.ActualError import ActualError
from test_suite.TestcaseVariation import TestcaseVariation


@dataclass(frozen=True)
class TestcaseResult:
    testcaseVariation: TestcaseVariation
    actualErrors: list[ActualError]
    diff: dict[str, int]
    passed: bool
    duration_seconds: float
