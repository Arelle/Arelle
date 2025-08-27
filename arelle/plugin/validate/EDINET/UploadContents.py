"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ReportFolderType import ReportFolderType


@dataclass(frozen=True)
class UploadContents:
    reports: dict[ReportFolderType, frozenset[Path]]
    uploadPaths: dict[Path, UploadPathInfo]


@dataclass(frozen=True)
class UploadPathInfo:
    isAttachment: bool
    isCorrection: bool
    isCoverPage: bool
    isDirectory: bool
    isRoot: bool
    isSubdirectory: bool
    reportFolderType: ReportFolderType | None
