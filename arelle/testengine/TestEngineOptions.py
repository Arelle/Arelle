"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arelle.testengine.ErrorLevel import ErrorLevel
from arelle.testengine.TestcaseConstraint import TestcaseConstraint


@dataclass(frozen=True)
class TestEngineOptions:
    index_file: str
    additional_constraints: list[tuple[str, list[TestcaseConstraint]]] = field(default_factory=list)
    compare_formula_output: bool = False
    custom_compare_patterns: list[tuple[str, str]] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    ignore_levels: frozenset[ErrorLevel] = field(default_factory=frozenset)
    log_directory: Path | None = None
    match_all: bool = True
    name: str | None = None
    options: dict[str, Any] = field(default_factory=dict)
    parallel: bool = False
