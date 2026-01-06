"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arelle.testengine.TestcaseVariation import TestcaseVariation


@dataclass(frozen=True)
class TestcaseVariationSet:
    load_errors: list[Any]
    skipped_testcase_variations: list[TestcaseVariation]
    testcase_variations: list[TestcaseVariation]
