"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable
from typing import Any, cast, IO

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

    Note: Sample instances from EDINET almost always violate this rule based on our
    current interpretation. The exception being files placed outside the XBRL directory,
    i.e. ammendment documents. For now, we will only check ammendment documents, directory
    names, or other files in unexpected locations.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    uploadContents = pluginData.getUploadContents(val.modelXbrl)
    paths = set(uploadContents.directories | uploadContents.unknownPaths)
    for ammendmentPaths in uploadContents.ammendmentPaths.values():
        paths.update(ammendmentPaths)
    for path in paths:
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
    """
    if not pluginData.shouldValidateUpload(val):
        return
    uploadFilepaths = pluginData.getUploadFilepaths(val.modelXbrl)
    emptyDirectories = []
    for path in uploadFilepaths:
        if path.suffix:
            continue
        if not any(path in p.parents for p in uploadFilepaths):
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
def rule_EC0132E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0132E: Store the manifest file directly under the relevant folder.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    uploadFilepaths = pluginData.getUploadFilepaths(val.modelXbrl)
    docFolders = ("PublicDoc", "PrivateDoc", "AuditDoc")
    for filepath in uploadFilepaths:
        if filepath.name not in docFolders:
            continue
        expectedManifestName = f'manifest_{filepath.name}.xml'
        expectedManifestPath = filepath / expectedManifestName
        if expectedManifestPath in uploadFilepaths:
            continue
        yield Validation.error(
            codes='EDINET.EC0132E',
            msg=_("'%(expectedManifestName)s' does not exist in '%(expectedManifestFolder)s'. "
                  "Please store the manifest file (or cover file) directly under the relevant folder and upload it again. "),
            expectedManifestName=expectedManifestName,
            expectedManifestFolder=str(filepath),
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
    if not pluginData.shouldValidateUpload(val):
        return
    zipFile = cast(zipfile.ZipFile, val.modelXbrl.fileSource.fs)
    file = cast(IO[Any], zipFile.fp)
    file.seek(0, 2)  # Move to the end of the file
    size = file.tell()
    if size > 55 * 1000 * 1000:  # Interpretting MB as megabytes (1,000,000 bytes)
        yield Validation.error(
            codes='EDINET.EC0183E',
            msg=_("The compressed file size exceeds 55MB. "
                  "Please compress the file to a size of 55MB or less and upload it again."),
        )
