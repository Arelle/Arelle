"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .InstanceType import InstanceType


@dataclass(frozen=True)
class UploadContents:
    instances: dict[InstanceType, frozenset[Path]]
    uploadPaths: dict[Path, UploadPathInfo]


@dataclass(frozen=True)
class UploadPathInfo:
    instanceType: InstanceType | None
    isAttachment: bool
    isCorrection: bool
    isCoverPage: bool
    isDirectory: bool
    isRoot: bool
    isSubdirectory: bool
