"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .InstanceType import InstanceType


@dataclass(frozen=True)
class UploadContents:
    amendmentPaths: dict[InstanceType, frozenset[Path]]
    directories: frozenset[Path]
    instances: dict[InstanceType, frozenset[Path]]
    rootPaths: frozenset[Path]
    unknownPaths: frozenset[Path]
