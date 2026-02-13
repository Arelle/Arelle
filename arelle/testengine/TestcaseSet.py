"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arelle.testengine.Testcase import Testcase


@dataclass(frozen=True)
class TestcaseSet:
    load_errors: list[str]
    skipped_testcases: list[Testcase]
    testcases: list[Testcase]
