"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..FormType import FormType, HTML_EXTENSIONS, IMAGE_EXTENSIONS
from ..Manifest import parseManifests
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

FILE_COUNT_LIMITS = {
    Path("AttachDoc"): 990,
    Path("AuditDoc"): 990,
    Path("PrivateDoc"): 9_990,
    Path("PublicDoc"): 9_990,
    Path("XBRL") / "AttachDoc": 990,
    Path("XBRL") / "AuditDoc": 990,
    Path("XBRL") / "PrivateDoc": 9_990,
    Path("XBRL") / "PublicDoc": 9_990,
    Path("XBRL"): 99_990,
}

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
    i.e. amendment documents. For now, we will only check amendment documents, directory
    names, or other files in unexpected locations.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    uploadContents = pluginData.getUploadContents(val.modelXbrl)
    paths = set(uploadContents.directories | uploadContents.unknownPaths)
    for amendmentPaths in uploadContents.amendmentPaths.values():
        paths.update(amendmentPaths)
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
            # TODO: Do we validate amendment subfolders too? These aren't placed beneath the XBRL directory.
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
    for formType, amendmentPaths in uploadContents.amendmentPaths.items():
        for amendmentPath in amendmentPaths:
            isSubdirectory = amendmentPath.parent.name != formType.value
            checks.append((amendmentPath, True, formType, isSubdirectory))
    for formType, formPaths in uploadContents.forms.items():
        for amendmentPath in formPaths:
            isSubdirectory = amendmentPath.parent.name != formType.value
            checks.append((amendmentPath, False, formType, isSubdirectory))
    for path, isAmendment, formType, isSubdirectory in checks:
        ext = path.suffix
        if len(ext) == 0:
            continue
        validExtensions = formType.getValidExtensions(isAmendment, isSubdirectory)
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
    size = val.modelXbrl.fileSource.getBytesSize()
    if size is None:
        return  # File size is not available, cannot validate
    if size > 55_000_000:  # Interpretting MB as megabytes (1,000,000 bytes)
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0198E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0198E: The number of files in the total submission and directories can not exceed the upper limit.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    fileCounts: dict[Path, int] = defaultdict(int)
    uploadFilepaths = pluginData.getUploadFilepaths(val.modelXbrl)
    for path in uploadFilepaths:
        if len(path.suffix) == 0:
            continue
        for directory in FILE_COUNT_LIMITS.keys():
            if directory in path.parents:
                fileCounts[directory] += 1
                break
    for directory, limit in FILE_COUNT_LIMITS.items():
        actual = fileCounts[directory]
        if actual > limit:
            yield Validation.error(
                codes='EDINET.EC0198E',
                msg=_("The number of files in %(directory)s exceeds the upper limit (%(actual)s > %(limit)s). "
                      "Please reduce the number of files in the folder to below the maximum and try uploading again."),
                directory=str(directory),
                actual="{:,}".format(actual),
                limit="{:,}".format(limit),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0237E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0237E: The directory or file path to the lowest level exceeds the maximum value (259 characters).
    """
    if not pluginData.shouldValidateUpload(val):
        return
    uploadFilepaths = pluginData.getUploadFilepaths(val.modelXbrl)
    for path in uploadFilepaths:
        if len(str(path)) <= 259:
            continue
        yield Validation.error(
            codes='EDINET.EC0237E',
            msg=_("The directory or file path ('%(path)s') to the lowest level exceeds the maximum value (259 characters). "
                  "Please shorten the absolute path of the folder (or file) "
                  "to 259 characters or less and try uploading again."),
            path=str(path),
            file=str(path),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0206E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0206E: Empty files are not permitted.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    for path, size in pluginData.getUploadFileSizes(val.modelXbrl).items():
        if size > 0:
            continue
        yield Validation.error(
            codes='EDINET.EC0206E',
            msg=_("An empty file exists. "
                  "File name: '%(path)s'. "
                  "Please delete the empty file and upload again."),
            path=str(path),
            file=str(path),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1016E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1016E: The image file is over 300KB.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    for path, size in pluginData.getUploadFileSizes(val.modelXbrl).items():
        if path.suffix not in IMAGE_EXTENSIONS:
            continue
        if size <= 300_000:  # Interpretting KB as kilobytes (1,000 bytes)
            continue
        yield Validation.error(
            codes='EDINET.EC1016E',
            msg=_("The image file is over 300KB. "
                  "File name: '%(path)s'. "
                  "Please create an image file with a size of 300KB or less."),
            path=str(path),
            file=str(path),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1020E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1020E: When writing a DOCTYPE declaration, do not define it multiple times.
    Also, please modify the relevant file so that there is only one html tag, one head tag, and one body tag each.

    Note: Some violations of this rule (such as multiple DOCTYPE declarations) prevent Arelle from parsing
    the XML at all, and thus an XML schema error will be triggered rather than this validation error.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    checkNames = frozenset({'body', 'head', 'html'})
    for modelDocument in val.modelXbrl.urlDocs.values():
        path = Path(modelDocument.uri)
        if path.suffix not in HTML_EXTENSIONS:
            continue
        rootElt = modelDocument.xmlRootElement
        eltCounts = {
            rootElt.qname.localName: 1
        }
        for elt in rootElt.iterdescendants():
            name = elt.qname.localName
            if name not in checkNames:
                continue
            eltCounts[name] = eltCounts.get(name, 0) + 1
            pass
        if any(count > 1 for count in eltCounts.values()):
            yield Validation.error(
                codes='EDINET.EC1020E',
                msg=_("The HTML syntax is incorrect. "
                      "File name: '%(path)s'. "
                      "When writing a DOCTYPE declaration, do not define it multiple times. "
                      "Also, please modify the relevant file so that there is only one html tag, "
                      "one head tag, and one body tag each."),
                path=str(path),
                file=str(path),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_manifest_preferredFilename(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5804E: The preferredFilename attribute must be set on the instance
    element in the manifest file.

    EDINET.EC5805E: The instance file extension is not ".xbrl". File name: xxx
    Please change the extension of the instance name set in the preferredFilename
    attribute value of the instance element in the manifest file to ".xbrl".

    EDINET.EC5806E: The same instance file name is set multiple times. File name: xxx
    The preferredFilename attribute value of the instance element in the manifest
    file must be unique within the same file.
    """
    if not pluginData.shouldValidateUpload(val):
        return
    manifests = parseManifests(val.modelXbrl.fileSource)
    for manifest in manifests:
        preferredFilenames = set()
        duplicateFilenames = set()
        for instance in manifest.instances:
            if len(instance.preferredFilename) == 0:
                yield Validation.error(
                    codes='EDINET.EC5804E',
                    msg=_("The instance file name is not set. "
                          "Set the instance name as the preferredFilename attribute value "
                          "of the instance element in the manifest file. (manifest: '%(manifest)s', id: %(id)s)"),
                    manifest=str(manifest.path),
                    id=instance.id,
                )
                continue
            preferredFilename = Path(instance.preferredFilename)
            if preferredFilename.suffix != '.xbrl':
                yield Validation.error(
                    codes='EDINET.EC5805E',
                    msg=_("The instance file extension is not '.xbrl'. "
                          "File name: '%(preferredFilename)s'. "
                          "Please change the extension of the instance name set in the "
                          "preferredFilename attribute value of the instance element in "
                          "the manifest file to '.xbrl'. (manifest: '%(manifest)s', id: %(id)s)"),
                    preferredFilename=instance.preferredFilename,
                    manifest=str(manifest.path),
                    id=instance.id,
                )
                continue
            if instance.preferredFilename in preferredFilenames:
                duplicateFilenames.add(instance.preferredFilename)
                continue
            preferredFilenames.add(instance.preferredFilename)
        for duplicateFilename in duplicateFilenames:
            yield Validation.error(
                codes='EDINET.EC5806E',
                msg=_("The same instance file name is set multiple times. "
                      "File name: '%(preferredFilename)s'. "
                      "The preferredFilename attribute value of the instance "
                      "element in the manifest file must be unique within the "
                      "same file. (manifest: '%(manifest)s')"),
                manifest=str(manifest.path),
                preferredFilename=duplicateFilename,
            )
