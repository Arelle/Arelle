"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .ReportFolderType import ReportFolderType


@dataclass(frozen=True)
class UploadContents:
    reports: dict[ReportFolderType, frozenset[Path]]
    uploadPaths: list[UploadPathInfo]

    @property
    def sortedPaths(self) -> list[Path]:
        return sorted(uploadPath.path for uploadPath in self.uploadPaths)

    @cached_property
    def uploadPathsByFullPath(self) -> dict[Path, UploadPathInfo]:
        return {
            uploadPath.fullPath: uploadPath
            for uploadPath in self.uploadPaths
        }

    @cached_property
    def uploadPathsByPath(self) -> dict[Path, UploadPathInfo]:
        return {
            uploadPath.path: uploadPath
            for uploadPath in self.uploadPaths
        }


@dataclass(frozen=True)
class UploadPathInfo:
    fullPath: Path
    isAttachment: bool
    isCorrection: bool
    isCoverPage: bool
    isDirectory: bool
    isRoot: bool
    isSubdirectory: bool
    path: Path
    reportFolderType: ReportFolderType | None
    reportPath: Path | None
