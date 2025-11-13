"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from test_engine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestEngineOptions:
    additionalConstraints: list[tuple[str, list[TestcaseConstraint]]]
    filters: list[str]
    indexFile: str
    logDirectory: Path
    matchAll: bool
    options: dict[str, Any]
    parallel: bool
