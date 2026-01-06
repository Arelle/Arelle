"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

from arelle.testengine.TestcaseResult import TestcaseResult
from arelle.testengine.TestcaseSet import TestcaseSet


@dataclass(frozen=True)
class TestEngineResult:
    testcase_results: list[TestcaseResult]
    testcase_set: TestcaseSet
