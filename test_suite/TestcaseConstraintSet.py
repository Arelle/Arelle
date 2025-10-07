from dataclasses import dataclass

from test_suite.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestcaseConstraintSet:
    errors: list[TestcaseConstraint]
    matchAll: bool
