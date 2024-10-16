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

def getPackageTopLevelDirectories(filesource: FileSource) -> set[str]:
    return {e.partition("/")[0] for e in filesource.dir or [] if "/" in e}
