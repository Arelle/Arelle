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
from ..PluginValidationDataExtension import PluginValidationDataExtension, FormType, HTML_EXTENSIONS

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
def rule_EC0129E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0129E: Limit the number of subfolders to 3 or less from the XBRL directory.
    """
    startingDirectory = 'XBRL'
    if not pluginData.shouldValidateUpload(val):
        return
    uploadFilepaths = pluginData.getUploadFilepaths(val.modelXbrl)
    for path in uploadFilepaths:
        parents = [parent.name for parent in path.parents]
        if startingDirectory in parents:
            parents = parents[:parents.index(startingDirectory)]
        else:
            # TODO: Do we validate ammendment subfolders too? These aren't placed beneath the XBRL directory.
            continue
        depth = len(parents)
        if depth > 3:
            yield Validation.error(
                codes='EDINET.EC0129E',
                msg=_("The subordinate directories of %(path)s go up to the level %(depth)s (directories: %(parents)s). "
                      "Please limit the number of subfolders to 3 or less and upload again."),
                path=str(path),
                depth=depth,
                parents=', '.join(f"'{parent}'" for parent in reversed(parents)),
                file=str(path)
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0130E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0130E: File extensions must match the file extensions allowed in Figure 2-1-3 and Figure 2-1-5.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    uploadContents = pluginData.getUploadContents(val.modelXbrl)
    checks = []
    for formType, ammendmentPaths in uploadContents.ammendmentPaths.items():
        for ammendmentPath in ammendmentPaths:
            isSubdirectory = ammendmentPath.parent.name != formType.value
            checks.append((ammendmentPath, True, formType, isSubdirectory))
    for formType, formPaths in uploadContents.forms.items():
        for ammendmentPath in formPaths:
            isSubdirectory = ammendmentPath.parent.name != formType.value
            checks.append((ammendmentPath, False, formType, isSubdirectory))
    for path, isAmmendment, formType, isSubdirectory in checks:
        ext = path.suffix
        if len(ext) == 0:
            continue
        validExtensions = formType.getValidExtensions(isAmmendment, isSubdirectory)
        if validExtensions is None:
            continue
        if ext not in validExtensions:
            yield Validation.error(
                codes='EDINET.EC0130E',
                msg=_("The file extension '%(ext)s' is not valid at '%(path)s'. "
                      "Valid extensions at this location are: %(validExtensions)s. "
                      "Please change the file extension to a configurable extension and upload it again. "
                      "For information on configurable file extensions, please refer to 'Table 2-1-3 Storable File Formats (1)' "
                      "in the 'Document File Specifications' and 'Table 2-1-5 Storable File Formats (2)' in the "
                      "'Document File Specifications'."),
                ext=ext,
                path=str(path),
                validExtensions=', '.join(f"'{e}'" for e in validExtensions),
                file=str(path)
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
    uploadContents = pluginData.getUploadContents(val.modelXbrl)
    for formType in (FormType.AUDIT_DOC, FormType.PRIVATE_DOC, FormType.PUBLIC_DOC):
        if formType not in uploadContents.forms:
            continue
        if formType.manifestPath in uploadContents.forms.get(formType, []):
            continue
        yield Validation.error(
            codes='EDINET.EC0132E',
            msg=_("'%(expectedManifestName)s' does not exist in '%(expectedManifestDirectory)s'. "
                  "Please store the manifest file (or cover file) directly under the relevant folder and upload it again. "),
            expectedManifestName=formType.manifestPath.name,
            expectedManifestDirectory=str(formType.manifestPath.parent),
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0188E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0188E: There is an HTML file directly under PublicDoc or PrivateDoc whose first 7 characters are not numbers.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    pattern = re.compile(r'^\d{7}')
    uploadFilepaths = pluginData.getUploadFilepaths(val.modelXbrl)
    docFolders = frozenset({"PublicDoc", "PrivateDoc"})
    for path in uploadFilepaths:
        if path.suffix not in HTML_EXTENSIONS:
            continue
        if path.parent.name not in docFolders:
            continue
        if pattern.match(path.name) is None:
            yield Validation.error(
                codes='EDINET.EC0188E',
                msg=_("There is an html file directly under PublicDoc or PrivateDoc whose first 7 characters are not numbers: '%(path)s'."
                      "Please change the first 7 characters of the file name of the file directly under the folder to numbers "
                      "and upload it again."),
                path=str(path),
                file=str(path),
            )
