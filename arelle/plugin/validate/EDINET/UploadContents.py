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

    @property
    def sortedPaths(self) -> list[Path]:
        return sorted(self.uploadPaths.keys())


@dataclass(frozen=True)
class UploadPathInfo:
    isAttachment: bool
    isCorrection: bool
    isCoverPage: bool
    isDirectory: bool
    isRoot: bool
    isSubdirectory: bool
    path: Path
    reportFolderType: ReportFolderType | None
    reportPath: Path | None
