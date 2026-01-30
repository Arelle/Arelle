"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from arelle.testengine.ConstraintSet import ConstraintSet


@dataclass(frozen=True)
class Testcase:
    base: Path
    blocked_code_pattern: str
    calc_mode: str | None
    compare_instance_uri: Path | None
    description: str
    expected_instance_count: int | None
    full_id: str
    inline_target: str | None
    local_id: str
    name: str
    parameters: str
    read_first_uris: list[str]
    status: str
    constraint_set: ConstraintSet
