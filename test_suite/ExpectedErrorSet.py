from dataclasses import dataclass

from test_suite.ExpectedErrorConstraint import ExpectedErrorConstraint


@dataclass(frozen=True)
class ExpectedErrorSet:
    errors: list[ExpectedErrorConstraint]
    matchAll: bool
