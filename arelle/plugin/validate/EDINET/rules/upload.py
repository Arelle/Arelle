"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

FILENAME_STEM_PATTERN = re.compile(r'[a-zA-Z0-9_-]*')


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0121E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0121E: There is a directory or file that contains more than 31 characters
    or uses characters other than those allowed (alphanumeric characters, '-' and '_').

    Implementation note: getManifestDirectoryPaths results in this validation only
    considering files that are beneath the same directory as the manifest file that
    the given DTS originated from. This prevents duplicate errors for packages
    with multiple document sets, but can still cause duplicates when a single manifest
    file has multiple document sets, as is often the case with AuditDoc manifests.
    """
    manifestDirectoryPaths = pluginData.getManifestDirectoryPaths(val.modelXbrl)
    for path in manifestDirectoryPaths:
        if len(str(path.name)) > 31 or not FILENAME_STEM_PATTERN.match(path.stem):
            yield Validation.error(
                codes='EDINET.EC0121E',
                msg=_("There is a directory or file in '%(directory)s' that contains more than 31 characters "
                      "or uses characters other than those allowed (alphanumeric characters, '-' and '_'). "
                      "Directory or file name: '%(basename)s'. "
                      "Please change the file name (or folder name) to within 31 characters and to usable "
                      "characters, and upload again."),
                directory=str(path.parent),
                basename=path.name,
                file=str(path)
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0124E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0124E: There are no empty directories.

    See note on EC0121E.
    """
    manifestDirectoryPaths = pluginData.getManifestDirectoryPaths(val.modelXbrl)
    emptyDirectories = []
    for path in manifestDirectoryPaths:
        if path.suffix:
            continue
        if not any(path in p.parents for p in manifestDirectoryPaths):
            emptyDirectories.append(str(path))
    for emptyDirectory in emptyDirectories:
        yield Validation.error(
            codes='EDINET.EC0124E',
            msg=_("There is no file directly under '%(emptyDirectory)s'. "
                  "No empty folders. "
                  "Please store the file in the appropriate folder or delete the folder and upload again."),
            emptyDirectory=emptyDirectory,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0183E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0183E: The compressed file size exceeds 55MB.
    """
    if val.modelXbrl.fileSource is None:
        return
    if not isinstance(val.modelXbrl.fileSource.fs, zipfile.ZipFile):
        return
    zipFile = val.modelXbrl.fileSource.fs
    zipFile.fp.seek(0, 2)  # Move to the end of the file
    size = zipFile.fp.tell()
    if size > 55 * 1024 * 1024:
        yield Validation.error(
            codes='EDINET.EC0183E',
            msg=_("The compressed file size exceeds 55MB. "
                  "Please compress the file to a size of 55MB or less and upload it again."),
        )
