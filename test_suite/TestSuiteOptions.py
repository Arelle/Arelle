from dataclasses import dataclass
from typing import Any

from test_suite.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestSuiteOptions:
    additionalConstraints: list[tuple[str, list[TestcaseConstraint]]]
    filters: list[str]
    indexFile: str
    options: dict[str, Any]
    parallel: bool
