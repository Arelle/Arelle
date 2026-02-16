"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import zipfile

    from arelle.FileSource import FileSource


def isZipfileEncrypted(info: zipfile.ZipInfo) -> bool:
    return bool(info.flag_bits & 0x1)

def getPackageTopLevelFiles(filesource: FileSource) -> set[str]:
    return {e for e in filesource.dir or [] if "/" not in e}

def getPackageEntries(filesource: FileSource) -> set[str]:
    return {getSafePath(e) for e in filesource.dir or []}

def getPackageTopLevelDirectories(packageEntries: set[str]) -> set[str]:
    return {e.partition("/")[0] for e in packageEntries if "/" in e}

def getPackageTopLevelDirectoriesFromFileSource(filesource: FileSource) -> set[str]:
    return getPackageTopLevelDirectories(getPackageEntries(filesource))

def getSafePath(path: str) -> str:
    """
    Transforms input path into "safe" path to allow for minimum ReportPackage construction
    despite paths being invalid (e.g. leading slash, backslash).
    """
    return path.removeprefix('/').replace('\\', '/')
