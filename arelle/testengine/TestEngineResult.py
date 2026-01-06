"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

from arelle.testengine.TestcaseResult import TestcaseResult
from arelle.testengine.TestcaseVariationSet import TestcaseVariationSet


@dataclass(frozen=True)
class TestEngineResult:
    testcase_results: list[TestcaseResult]
    testcase_variation_set: TestcaseVariationSet
