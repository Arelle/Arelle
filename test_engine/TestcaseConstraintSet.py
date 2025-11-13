"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass

from test_engine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestcaseConstraintSet:
    constraints: list[TestcaseConstraint]
    matchAll: bool
