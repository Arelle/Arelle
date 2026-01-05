"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any

from test_engine.ErrorLevel import ErrorLevel
from test_engine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestEngineOptions:
    additionalConstraints: list[tuple[str, list[TestcaseConstraint]]]
    compareFormulaOutput: bool
    customComparePatterns: list[tuple[str, str]]
    filters: list[str]
    ignoreLevels: frozenset[ErrorLevel]
    indexFile: str
    logDirectory: Path | None
    matchAll: bool
    name: str | None
    options: dict[str, Any]
    parallel: bool
