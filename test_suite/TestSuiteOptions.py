from dataclasses import dataclass
from pathlib import Path
from typing import Any

from test_suite.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestSuiteOptions:
    additionalConstraints: list[tuple[str, list[TestcaseConstraint]]]
    filters: list[str]
    indexFile: str
    logDirectory: Path
    matchAll: bool
    options: dict[str, Any]
    parallel: bool
