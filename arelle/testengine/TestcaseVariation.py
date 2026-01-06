"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestcaseConstraintSet import TestcaseConstraintSet


@dataclass(frozen=True)
class TestcaseVariation:
    base: str
    blocked_code_pattern: str
    calc_mode: str | None
    compare_formula_output_uri: Path | None
    compare_instance_uri: Path | None
    description: str
    full_id: str
    id: str
    ignore_levels: frozenset[ErrorLevel]
    inline_target: str | None
    name: str
    parameters: str
    read_first_uris: list[str]
    report_count: int | None
    short_name: str
    status: str
    testcase_constraint_set: TestcaseConstraintSet
