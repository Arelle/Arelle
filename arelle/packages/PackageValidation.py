"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import os.path
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from arelle.packages import PackageUtils
from arelle.packages.PackageConst import META_INF_DIRECTORY
from arelle.packages.PackageType import PackageType
from arelle.typing import TypeGetText
from arelle.utils.validate.Validation import Validation

if TYPE_CHECKING:
    from arelle.FileSource import FileSource


_: TypeGetText


def validatePackageZipFormat(
    packageType: PackageType,
    filesource: FileSource,
) -> Validation | None:
    if filesource.dir is None:
        return Validation.error(
            codes=f"{packageType.errorPrefix}:invalidArchiveFormat",
            msg=_("%(packageType)s package is not valid and could not be opened: %(file)s"),
            packageType=packageType.name,
            file=os.path.basename(str(filesource.url)),
        )
    return None


def validatePackageNotEncrypted(
    packageType: PackageType,
    filesource: FileSource,
) -> Validation | None:
    if any(PackageUtils.isZipfileEncrypted(f) for f in getattr(filesource.fs, "filelist", [])):
        return Validation.error(
            codes=f"{packageType.errorPrefix}:invalidArchiveFormat",
            msg=_("%(packageType)s package contains encrypted files: %(file)s"),
            packageType=packageType.name,
            file=os.path.basename(str(filesource.url)),
        )
    return None


def validateZipFileSeparators(
    packageType: PackageType,
    filesource: FileSource,
) -> Validation | None:
    if filesource.isZipBackslashed:
        return Validation.error(
            codes=f"{packageType.errorPrefix}:invalidArchiveFormat",
            msg=_("%(packageType)s package directory uses '\\' as a file separator."),
            packageType=packageType.name,
            file=os.path.basename(str(filesource.url)),
        )
    return None


def validateTopLevelFiles(
    packageType: PackageType,
    filesource: FileSource,
) -> Validation | None:
    topLevelFiles = PackageUtils.getPackageTopLevelFiles(filesource)
    numTopLevelFiles = len(topLevelFiles)
    if numTopLevelFiles > 0:
        return Validation.error(
            codes=f"{packageType.errorPrefix}:invalidDirectoryStructure",
            msg=_("%(packageType)s package contains %(count)s top level file(s):  %(topLevelFiles)s"),
            packageType=packageType.name,
            count=numTopLevelFiles,
            topLevelFiles=", ".join(sorted(topLevelFiles)),
            file=os.path.basename(str(filesource.url)),
        )
    return None


def validateTopLevelDirectories(
    packageType: PackageType,
    filesource: FileSource,
) -> Validation | None:
    topLevelDirectories = PackageUtils.getPackageTopLevelDirectories(filesource)
    numTopLevelDirectories = len(topLevelDirectories)
    if numTopLevelDirectories == 0:
        return Validation.error(
            codes=f"{packageType.errorPrefix}:invalidDirectoryStructure",
            msg=_("%(packageType)s Package does not contain a top level directory"),
            packageType=packageType.name,
            file=os.path.basename(str(filesource.url)),
        )
    if numTopLevelDirectories > 1:
        return Validation.error(
            codes=f"{packageType.errorPrefix}:invalidDirectoryStructure",
            msg=_("%(packageType)s package contains %(count)s top level directories: %(topLevelDirectories)s"),
            packageType=packageType.name,
            count=numTopLevelDirectories,
            topLevelDirectories=", ".join(sorted(topLevelDirectories)),
            file=os.path.basename(str(filesource.url)),
        )
    return None


def validateMetadataDirectory(
    packageType: PackageType,
    filesource: FileSource,
) -> Validation | None:
    if not any(META_INF_DIRECTORY in f.split("/")[1:][:1] for f in filesource.dir or []):
        return Validation.error(
            codes=f"{packageType.errorPrefix}:metadataDirectoryNotFound",
            msg=_("%(packageType)s package top-level directory does not contain a subdirectory META-INF"),
            packageType=packageType.name,
            file=os.path.basename(str(filesource.url)),
        )
    return None
