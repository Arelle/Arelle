"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass

from arelle.testengine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestcaseConstraintSet:
    constraints: list[TestcaseConstraint]
    match_all: bool
