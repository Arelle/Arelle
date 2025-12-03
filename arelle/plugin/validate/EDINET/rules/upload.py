"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import regex

from arelle import UrlUtil, XbrlConst
from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.ModelDocument import Type as ModelDocumentType
from arelle.ModelInstanceObject import ModelFact, ModelInlineFact
from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidateConst import VALID

from ..Constants import JAPAN_LANGUAGE_CODES
from ..DisclosureSystems import DISCLOSURE_SYSTEM_EDINET
from ..FilingFormat import Ordinance, Taxonomy
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..ReportFolderType import HTML_EXTENSIONS, IMAGE_EXTENSIONS, ReportFolderType

if TYPE_CHECKING:
    from ..ControllerPluginData import ControllerPluginData

_: TypeGetText

ALLOWED_ROOT_FOLDERS = {
    "AttachDoc",
    "AuditDoc",
    "PrivateAttach",
    "PrivateDoc",
    "PublicAttach",
    "PublicDoc",
    "XBRL",
}

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

FILENAME_STEM_PATTERN = regex.compile(r'[a-zA-Z0-9_-]*')


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0100E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0100E: An illegal directory is found directly under the transferred directory.
    Only the following root folders are allowed:
        AttachDoc
        AuditDoc*
        PrivateAttach
        PrivateDoc*
        PublicAttach
        PublicDoc*
        XBRL
    * Only when reporting corrections

    NOTE: since we do not have access to the submission type, we can't determine if the submission is a correction or not.
    For this implementation, we will allow all directories that may be valid for at least one submission type.
    This allows for a false-negative outcome when a non-correction submission has a correction-only root directory.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        if pathInfo.isRoot and path.name not in ALLOWED_ROOT_FOLDERS:
            yield Validation.error(
                codes='EDINET.EC0100E',
                msg=_("An illegal directory is found directly under the transferred directory. "
                      "Directory name or file name: '%(rootDirectory)s'. "
                      "Delete all folders except the following folders that exist directly "
                      "under the root folder, and then upload again: %(allowedDirectories)s."),
                rootDirectory=path.name,
                allowedDirectories=', '.join(f"'{d}'" for d in ALLOWED_ROOT_FOLDERS)
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0124E_EC0187E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0124E: There are no empty root directories.
    EDINET.EC0187E: There are no empty subdirectories.
    """
    uploadFilepaths = pluginData.getUploadFilepaths(fileSource)
    emptyDirectories = []
    for path, zipPath in uploadFilepaths.items():
        if not zipPath.is_dir():
            continue
        if not any(path in p.parents for p in uploadFilepaths):
            emptyDirectories.append(path)
    for emptyDirectory in emptyDirectories:
        if len(emptyDirectory.parts) <= 1:
            yield Validation.error(
                codes='EDINET.EC0124E',
                msg=_("There is no file directly under '%(emptyDirectory)s'. "
                      "No empty root folders. "
                      "Please store the file in the appropriate folder or delete the folder and upload again."),
                emptyDirectory=str(emptyDirectory),
            )
        else:
            yield Validation.error(
                codes='EDINET.EC0187E',
                msg=_("'%(parentDirectory)s' contains a subordinate directory ('%(emptyDirectory)s') with no files. "
                      "Please store the file in the corresponding subfolder or delete the subfolder and upload again."),
                parentDirectory=str(emptyDirectory.parent),
                emptyDirectory=str(emptyDirectory),
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0129E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0129E: Limit the number of subfolders to 3 or less from the XBRL directory.
    """
    startingDirectory = 'XBRL'
    uploadFilepaths = pluginData.getUploadFilepaths(fileSource)
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
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0130E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0130E: File extensions must match the file extensions allowed in Figure 2-1-3 and Figure 2-1-5.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        if pathInfo.reportFolderType is None or pathInfo.isDirectory:
            continue
        validExtensions = pathInfo.reportFolderType.getValidExtensions(pathInfo.isCorrection, pathInfo.isSubdirectory)
        if validExtensions is None:
            continue
        ext = path.suffix
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
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0132E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0132E: Cover page or manifest file is missing.

    Note: Cover page is not required in AuditDoc.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for reportFolderType, paths in uploadContents.reports.items():
        if reportFolderType.isAttachment:
            # These rules don't apply to "Attach" directories
            continue
        coverPageFound = False
        manifestFound = False
        for path in paths:
            pathInfo = uploadContents.uploadPathsByPath[path]
            if pathInfo.isCoverPage:
                coverPageFound = True
            if path == reportFolderType.manifestPath:
                manifestFound = True
        if not coverPageFound and reportFolderType != ReportFolderType.AUDIT_DOC:
            yield Validation.error(
                codes='EDINET.EC0132E',
                msg=_("Cover page does not exist in '%(expectedManifestDirectory)s'. "
                      "Please store the cover file directly under the relevant folder and upload it again. "),
                expectedManifestDirectory=str(reportFolderType.manifestPath.parent),
            )
        if not manifestFound:
            yield Validation.error(
                codes='EDINET.EC0132E',
                msg=_("'%(expectedManifestName)s' does not exist in '%(expectedManifestDirectory)s'. "
                      "Please store the manifest file directly under the relevant folder and upload it again. "),
                expectedManifestName=reportFolderType.manifestPath.name,
                expectedManifestDirectory=str(reportFolderType.manifestPath.parent),
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0183E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0183E: The compressed file size exceeds 55MB.
    """
    size = fileSource.getBytesSize()
    if size is None:
        return  # File size is not available, cannot validate
    if size > 55_000_000:  # Interpretting MB as megabytes (1,000,000 bytes)
        yield Validation.error(
            codes='EDINET.EC0183E',
            msg=_("The compressed file size exceeds 55MB. "
                  "Please compress the file to a size of 55MB or less and upload it again."),
        )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0188E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0188E: There is an HTML file directly under PublicDoc or PrivateDoc whose first 7 characters are not numbers.
    """
    pattern = regex.compile(r'^\d{7}')
    uploadFilepaths = pluginData.getUploadFilepaths(fileSource)
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
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0192E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0192E: The cover file for PrivateDoc cannot be set because it uses a
    PublicDoc cover file. Please delete the cover file from PrivateDoc and upload
    it again.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        if not pathInfo.isCoverPage:
            continue
        # Only applies to PrivateDoc correction reports
        if pathInfo.isCorrection and pathInfo.reportFolderType == ReportFolderType.PRIVATE_DOC:
            yield Validation.error(
                codes='EDINET.EC0192E',
                msg=_("The cover file for PrivateDoc ('%(file)s') cannot be set because it uses a PublicDoc cover file. "
                      "Please delete the cover file from PrivateDoc and upload it again."),
                file=str(path),
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0198E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0198E: The number of files in the total submission and directories can not exceed the upper limit.
    """
    fileCounts: dict[Path, int] = defaultdict(int)
    uploadFilepaths = pluginData.getUploadFilepaths(fileSource)
    for path, zipPath in uploadFilepaths.items():
        if zipPath.is_dir():
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
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0233E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0233E: There is a file in the report directory that comes before the cover file
    in file name sort order.

    NOTE: This includes files in subdirectories. For example, PublicDoc/00000000_images/image.png
    comes before PublicDoc/0000000_header_*.htm
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    directories = defaultdict(list)
    for path in uploadContents.sortedPaths:
        pathInfo = uploadContents.uploadPathsByPath[path]
        if pathInfo.isDirectory:
            continue
        if pathInfo.reportFolderType in (ReportFolderType.PRIVATE_DOC, ReportFolderType.PUBLIC_DOC):
            directories[pathInfo.reportPath].append(pathInfo)
    for reportPath, pathInfos in directories.items():
        coverPagePath = next(iter(p for p in pathInfos if p.isCoverPage), None)
        if coverPagePath is None:
            continue
        errorPathInfos = pathInfos[:pathInfos.index(coverPagePath)]
        for pathInfo in errorPathInfos:
            yield Validation.error(
                codes='EDINET.EC0233E',
                msg=_("There is a file in the report directory in '%(reportPath)s' that comes before the cover "
                      "file ('%(coverPage)s') in file name sort order. "
                      "Directory name or file name: '%(path)s'. "
                      "Please make sure that there are no files that come before the cover file in the file "
                      "name sort order, and then upload again."),
                reportPath=str(reportPath),
                coverPage=str(coverPagePath.path.name),
                path=str(pathInfo.path),
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0234E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0234E: A cover file exists in an unsupported subdirectory.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        if pathInfo.isDirectory:
            continue
        if pathInfo.reportFolderType not in (ReportFolderType.PRIVATE_DOC, ReportFolderType.PUBLIC_DOC):
            continue
        if pathInfo.isSubdirectory and pathInfo.isCoverPage:
            yield Validation.error(
                codes='EDINET.EC0234E',
                msg=_("A cover file ('%(coverPage)s') exists in an unsupported subdirectory. "
                      "Directory: '%(directory)s'. "
                      "Please make sure there is no cover file in the subfolder and upload again."),
                coverPage=str(path.name),
                directory=str(path.parent),
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0237E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0237E: The directory or file path to the lowest level exceeds the maximum value (259 characters).
    """
    uploadFilepaths = pluginData.getUploadFilepaths(fileSource)
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
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0206E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0206E: Empty files are not permitted.
    """
    for path, size in pluginData.getUploadFileSizes(fileSource).items():
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
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0349E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0349E: An unexpected directory or file exists directly beneath the XBRL directory.
    Only PublicDoc, PrivateDoc, or AuditDoc directories may exist directly beneath the XBRL directory.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    xbrlDirectoryPath = Path('XBRL')
    allowedPaths = {p.xbrlDirectory for p in (
        ReportFolderType.AUDIT_DOC,
        ReportFolderType.PRIVATE_DOC,
        ReportFolderType.PUBLIC_DOC,
    )}
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        if path.parent != xbrlDirectoryPath:
            continue
        if path not in allowedPaths:
            yield Validation.error(
                codes='EDINET.EC0349E',
                msg=_("An unexpected directory or file exists directly beneath the XBRL directory. "
                      "Directory or file name: '%(file)s'."),
                file=path.name,
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC0352E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0352E: An XBRL file with an invalid name exists.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        if (
            pathInfo.isDirectory or
            pathInfo.isCorrection or
            pathInfo.isSubdirectory or
            pathInfo.isAttachment or
            pathInfo.reportFolderType is None or
            any(path == t.manifestPath for t in ReportFolderType)
        ):
            continue
        patterns = pathInfo.reportFolderType.ixbrlFilenamePatterns
        if not any(pattern.fullmatch(path.name) for pattern in patterns):
            yield Validation.error(
                codes='EDINET.EC0352E',
                msg=_("A file with an invalid name exists. "
                      "File path: '%(path)s'."),
                path=str(path),
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_cover_items(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1000E: Cover page must contain "【表紙】".
    EDINET.EC1001E: A required item is missing from the cover page.
    EDINET.EC1002E: A duplicate item is included on the cover page.
    EDINET.EC1003E: An unnecessary item is included on the cover page.
    EDINET.EC1004E: An item on the cover page is out of order.
    EDINET.EC1005E: A required item on the cover page is missing a valid value.
    """
    uploadContents = pluginData.getUploadContents(val.modelXbrl)
    if uploadContents is None:
        return
    for url, doc in val.modelXbrl.urlDocs.items():
        path = Path(url)
        pathInfo = uploadContents.uploadPathsByFullPath.get(path)
        if pathInfo is None or not pathInfo.isCoverPage:
            continue
        rootElt = doc.xmlRootElement
        coverPageTextFound = False
        for elt in rootElt.iterdescendants():
            if not coverPageTextFound and elt.text and '【表紙】' in elt.text:
                coverPageTextFound = True
                break
        if not coverPageTextFound:
            yield Validation.error(
                codes='EDINET.EC1000E',
                msg=_("There is no '【表紙】' on the cover page. "
                      "File name: '%(file)s'. "
                      "Please add '【表紙】' to the relevant file."),
                file=doc.basename,
            )
        filingFormat = pluginData.getFilingFormat(val.modelXbrl)
        if filingFormat is None:
            return
        allCoverItems = pluginData.getCoverItems(val.modelXbrl)
        requiredCoverItems = pluginData.getCoverItemRequirements(val.modelXbrl)
        if requiredCoverItems is None:
            return
        prohibitedCoverItems = allCoverItems - set(requiredCoverItems)
        sequenceQueue = list(requiredCoverItems)

        ixNStag = doc.ixNStag
        rootElt = doc.xmlRootElement
        foundFactsByQname = defaultdict(list)
        outOfSequence = False
        seenInSequence = set()
        for elt in rootElt.iterdescendants(ixNStag + "nonNumeric", ixNStag + "nonFraction", ixNStag + "fraction"):
            if not isinstance(elt, ModelFact):
                continue
            if not elt.qname in allCoverItems:
                continue
            if elt.qname in prohibitedCoverItems:
                yield Validation.error(
                    codes='EDINET.EC1003E',
                    msg=_("Cover item %(localName)s is not necessary. "
                          "File name: '%(file)s' (line %(line)s). "
                          "Please add the cover item %(localName)s to the relevant file."),
                    localName=elt.qname.localName,
                    file=doc.basename,
                    line=elt.sourceline,
                    modelObject=elt,
                )
                continue
            foundFactsByQname[elt.qname].append(elt)
            if elt.qname in seenInSequence:
                yield Validation.error(
                    codes='EDINET.EC1002E',
                    msg=_("Cover item %(localName)s is duplicated. "
                          "File name: '%(file)s'. "
                          "Please check the cover item %(localName)s of the relevant file "
                          "and make sure there are no duplicates."),
                    localName=elt.qname.localName,
                    file=doc.basename,
                    modelObject=elt,
                )
                continue
            seenInSequence.add(elt.qname)
            if len(sequenceQueue) == 0:
                continue
            if outOfSequence:
                continue
            if not sequenceQueue[0] == elt.qname:
                outOfSequence = True
                yield Validation.error(
                    codes='EDINET.EC1004E',
                    msg=_("Cover item %(localName)s is not in the correct order. "
                          "File name: '%(file)s'. "
                          "Please correct the order of cover items in the appropriate file."),
                    localName=elt.qname.localName,
                    file=doc.basename,
                    modelObject=elt,
                )
            if elt.qname in sequenceQueue:
                sequenceQueue.remove(elt.qname)

        for qname in requiredCoverItems:
            foundFacts = foundFactsByQname.get(qname, [])
            # No facts found.
            if len(foundFacts) == 0:
                yield Validation.error(
                    codes='EDINET.EC1001E',
                    msg=_("Cover item %(localName)s is missing. "
                          "File name: '%(file)s'. "
                          "Please add the cover item %(localName)s to the relevant file."),
                    localName=qname.localName,
                    file=doc.basename,
                )
            # Fact(s) found, but no valid, non-nil value.
            elif not any(f.xValid >= VALID and not f.isNil for f in foundFacts):
                yield Validation.error(
                    codes='EDINET.EC1005E',
                    msg=_("Cover item %(localName)s is missing a valid value. "
                          "File name: '%(file)s'. "
                          "Please enter a valid value for %(localName)s in the relevant file."),
                    localName=qname.localName,
                    file=doc.basename,
                    modelObject=foundFacts,
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1006E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1006E: Prohibited tag is used in HTML.
    """
    for doc in val.modelXbrl.urlDocs.values():
        for elt in pluginData.getProhibitedTagElements(doc):
            yield Validation.error(
                codes='EDINET.EC1006E',
                msg=_("Prohibited tag (%(tag)s) is used in HTML. File name: %(file)s (line %(line)s). "
                      "Please correct the prohibited tags for the relevant files. "
                      "For information on prohibited tags, please refer to \"4-1-4 Prohibited Rules\" "
                      "in the Validation Guidelines."),
                tag=elt.qname.localName,
                file=doc.basename,
                line=elt.sourceline,
                modelObject=elt,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_uri_references(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1007E: A URI in an HTML file must not be a URL or absolute path.
    EDINET.EC1013E: A URI in an HTML file directly beneath a report folder
        must specify a path under a subdirectory.
    EDINET.EC1014E: A URI in an HTML file must not specify a path to a directory.
    EDINET.EC1015E: A URI in an HTML file within a subdirectory
        must not specify a path directly beneath the report folder.
    EDINET.EC1021E: A URI in an HTML file must not specify a path to a file that doesn't exist.
    EDINET.EC1023E: A URI in an HTML file must not specify a path to a PDF file.
    EDINET.EC1035E: A URI in an HTML file must not specify a path to a location higher than the report path.

    Note: See "図表 3-4-8 PublicDoc フォルダ全体のイメージ" in "File Specification for EDINET".
    """
    uploadContents = pluginData.getUploadContents(val.modelXbrl)
    if uploadContents is None:
        return
    for uriReference in pluginData.uriReferences:
        if UrlUtil.isAbsolute(uriReference.attributeValue):
            yield Validation.error(
                codes='EDINET.EC1007E',
                msg=_("The URI in the HTML specifies a URL or absolute path. "
                      "File name: '%(file)s' (line %(line)s). "
                      "Please change the links in the files to relative paths."),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue

        uriPath = Path(uriReference.attributeValue)
        documentFullPath = Path(uriReference.document.uri)
        referenceFullPath = (documentFullPath.parent / uriPath).resolve()
        documentPathInfo = uploadContents.uploadPathsByFullPath.get(documentFullPath)
        assert documentPathInfo is not None # Should always be present, as it must exist to have a uriReference discovered.
        reportFullPath = Path(str(val.modelXbrl.fileSource.baseurl)) / (documentPathInfo.reportPath or "")

        if reportFullPath not in referenceFullPath.parents:
            yield Validation.error(
                codes='EDINET.EC1035E',
                msg=_("The URI in the HTML specifies a path that navigates "
                      "outside of the report folder '%(reportPath)s'. "
                      "File name: '%(file)s' (line %(line)s). "
                      "You cannot create a link from a subfolder to a parent folder. "
                      "Please delete the link."),
                reportPath=str(documentPathInfo.reportPath),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue

        if not documentPathInfo.isSubdirectory:
            if documentFullPath.parent not in referenceFullPath.parent.parents:
                yield Validation.error(
                    codes='EDINET.EC1013E',
                    msg=_("The URI in the HTML file directly beneath '%(reportPath)s' "
                          "specifies a path not under a subdirectory. "
                          "File name: '%(file)s' (line %(line)s). "
                          "Please move the referenced file into a subfolder beneath "
                          "'%(reportPath)s', or correct the URI."),
                    reportPath=str(documentPathInfo.reportPath),
                    file=uriReference.document.basename,
                    line=uriReference.element.sourceline,
                    modelObject=uriReference.element,
                )
                continue

        elif referenceFullPath.parent == reportFullPath:
            yield Validation.error(
                codes='EDINET.EC1015E',
                msg=_("The URI in the HTML file within a subdirectory specifies a "
                      "path to a file located directly beneath '%(reportPath)s'. "
                      "File name: '%(file)s' (line %(line)s). "
                      "You cannot create a link from a subfolder to this parent folder. "
                      "Please correct the relevant link."),
                reportPath=str(documentPathInfo.reportPath),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue

        referencePathInfo = uploadContents.uploadPathsByFullPath.get(referenceFullPath)
        if referencePathInfo is not None and referencePathInfo.isDirectory:
            yield Validation.error(
                codes='EDINET.EC1014E',
                msg=_("The URI in the HTML specifies a path to a directory. "
                      "File name: '%(file)s' (line %(line)s). "
                      "Please update the URI to reference a file."),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue

        if referenceFullPath.suffix.lower() == '.pdf':
            yield Validation.error(
                codes='EDINET.EC1023E',
                msg=_("The URI in the HTML specifies a path to a PDF file. "
                      "File name: '%(file)s' (line %(line)s). "
                      "Please remove the link from the relevant file."),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue

        if not val.modelXbrl.fileSource.exists(str(referenceFullPath)):
            yield Validation.error(
                codes='EDINET.EC1021E',
                msg=_("The linked file ('%(path)s') does not exist. "
                      "File name: '%(file)s' (line %(line)s). "
                      "Please update the URI to reference a file."),
                path=str(uriPath),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1009R(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1009R: The HTML file size must be 2.5MB (megabytes) or less.
    """
    for path, size in pluginData.getUploadFileSizes(fileSource).items():
        if path.suffix not in HTML_EXTENSIONS:
            continue
        if size > 2_500_000:
            yield Validation.warning(
                codes='EDINET.EC1009R',
                msg=_("The HTML file size exceeds the maximum limit. "
                      "File name: '%(path)s'. "
                      "Please split the file so that the file size is 2.5MB or less."),
                path=str(path),
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1016E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1016E: The image file is over 300KB.
    """
    for path, size in pluginData.getUploadFileSizes(fileSource).items():
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
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC1017E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1017E: There is an unused file.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    existingSubdirectoryFilepaths = {
        path
        for path, pathInfo in uploadContents.uploadPathsByPath.items()
        if pathInfo.isSubdirectory and not pathInfo.isDirectory
    }
    usedFilepaths = pluginData.getUsedFilepaths()
    unusedSubdirectoryFilepaths = existingSubdirectoryFilepaths - usedFilepaths
    for path in unusedSubdirectoryFilepaths:
        yield Validation.error(
            codes='EDINET.EC1017E',
            msg=_("There is an unused file. "
                  "File name: '%(file)s'. "
                  "Please remove the file or reference it in the HTML."),
            file=str(path),
        )


@validation(
    hook=ValidationHook.COMPLETE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_toc(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Performs validation via controller-level TableOfContentsBuilder.
    """
    tocBuilder = pluginData.getTableOfContentsBuilder()
    yield from tocBuilder.validate()


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_toc_pre(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Doesn't perform validations, but prepares data for TableOfContentsBuilder.
    """
    manifestInstance = pluginData.getManifestInstance(val.modelXbrl)
    if manifestInstance is not None and manifestInstance.type == ReportFolderType.PUBLIC_DOC.value:
        pluginData.addToTableOfContents(val.modelXbrl)
    return iter(())


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_html_elements(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1011E: The HTML lang attribute is not Japanese.
    EDINET.EC1020E: When writing a DOCTYPE declaration, do not define it multiple times.
        Also, please modify the relevant file so that there is only one html tag, one head tag, and one body tag each.

    Note: Some violations of EC1020E (such as multiple DOCTYPE declarations) prevent Arelle from parsing
    the XML at all, and thus an XML schema error will be triggered rather than this validation error.
    """
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
            if not isinstance(elt, ModelObject):
                continue
            name = elt.qname.localName
            if name in checkNames:
                eltCounts[name] = eltCounts.get(name, 0) + 1
            if not isinstance(elt, ModelFact):
                lang = elt.get(XbrlConst.qnXmlLang.clarkNotation)
                if lang is not None and lang not in JAPAN_LANGUAGE_CODES:
                    yield Validation.error(
                        codes='EDINET.EC1011E',
                        msg=_("The language setting is not Japanese. "
                              "File name: %(file)s (line %(line)s). "
                              "Please set the lang attribute on the given line of the "
                              "relevant file to one of the following: %(langValues)s."),
                        file=modelDocument.basename,
                        line=elt.sourceline,
                        langValues=', '.join(JAPAN_LANGUAGE_CODES),
                    )

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
def rule_EC1031E(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC1031E: Prohibited attribute is used in HTML.
    """
    for doc in val.modelXbrl.urlDocs.values():
        for elt, attributeName in pluginData.getProhibitedAttributeElements(doc):
            yield Validation.error(
                codes='EDINET.EC1031E',
                msg=_("Prohibited attribute '%(attributeName)s' is used in HTML. "
                      "File name: %(file)s (line %(line)s). "
                      "Please correct the tag attributes of the relevant file."),
                attributeName=attributeName,
                file=doc.basename,
                line=elt.sourceline,
                modelObject=elt,
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC5032E(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC5032E: A manifest file for an IFRS submission must not define multiple instances.
    """
    instances = pluginData.getManifestInstances()
    instancesByManifest = defaultdict(list)
    for instance in instances:
        instancesByManifest[instance.path].append(instance)
    for manifestPath, instances in instancesByManifest.items():
        if len(instances) < 2:
            continue
        for instance in instances:
            if instance.filingFormat is None:
                continue
            if (
                    instance.filingFormat.ordinance == Ordinance.IFRS or
                    Taxonomy.IFRS in instance.filingFormat.taxonomies
            ):
                yield Validation.error(
                    codes='EDINET.EC5032E',
                    msg=_("A manifest file for an IFRS submission defines multiple instances. "
                          "File: '%(path)s'. "
                          "If you use the IFRS taxonomy, please specify only one instance."),
                    path=str(manifestPath),
                )
                break


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8023W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8023W: In IXBRL files, 'nonFraction' elements should be immediately preceded by
    '△' if and only if the sign attribute is '-'.

    * Tagging using International Financial Reporting Standards taxonomy elements is not checked.
    * Tagging using Japanese GAAP notes or IFRS financial statement filer-specific additional elements
        may be identified as an exception and a warning displayed, even if the data content is correct.

    Note: This implementation interprets "immediately preceded" to mean that the symbol is present in the text
    immediately before the target element, not nested within, or separated by, siblings elements. The use of
    this symbol in sample filings support this interpretation.
    """
    negativeChar = '△'
    for fact in val.modelXbrl.facts:
        if not isinstance(fact, ModelInlineFact):
            continue
        if fact.localName != 'nonFraction':
            continue
        if fact.qname.namespaceURI == pluginData.namespaces.jpigp:
            continue

        precedingChar = None
        precedingSibling = fact.getprevious()
        # Check for the tail of the preceding sibling first.
        if precedingSibling is not None:
            if precedingSibling.tail:
                strippedText = precedingSibling.tail.strip()
                if strippedText:
                    precedingChar = strippedText[-1]
        # If nothing found, check the parent element if this is the first child.
        elif (parent := fact.getparent()) is not None:
            if fact == list(parent)[0] and parent.text:
                strippedText = parent.text.strip()
                if strippedText:
                    precedingChar = strippedText[-1]

        if fact.sign == '-' :
            if precedingChar != negativeChar:
                yield Validation.error(
                    codes='EDINET.EC8023W',
                    msg=_("In an inline XBRL file, if the sign attribute of the ix:nonFraction "
                          "element is set to \"-\" (minus), you must set \"△\" immediately "
                          "before the ix:nonFraction element tag."),
                    modelObject=fact,
                )
        else:
            if precedingChar == negativeChar:
                yield Validation.error(
                    codes='EDINET.EC8023W',
                    msg=_("In an inline XBRL file, if the sign attribute of the ix:nonFraction "
                          "element is not set to \"-\" (minus), there is no need to set \"△\" "
                          "immediately before the ix:nonFraction element tag."),
                    modelObject=fact,
                )



@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_filenames(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC0121E: There is a directory or file that contains
    more than 31 characters or uses characters other than those allowed (alphanumeric characters,
    '-' and '_').
    Note: Applies to everything EXCEPT files directly beneath non-correction report folders.

    EDINET.EC0200E: There is a file that uses characters other
    than those allowed (alphanumeric characters, '-' and '_').
    Note: Applies ONLY to files directly beneath non-correction report folders.
    """
    uploadContents = pluginData.getUploadContents()
    if uploadContents is None:
        return
    for path, pathInfo in uploadContents.uploadPathsByPath.items():
        isReportFile = (
                not pathInfo.isAttachment and
                not pathInfo.isCorrection and
                not pathInfo.isDirectory and
                not pathInfo.isSubdirectory
        )
        charactersAreValid = FILENAME_STEM_PATTERN.fullmatch(path.stem)
        lengthIsValid = isReportFile or (len(path.name) <= 31)
        if charactersAreValid and lengthIsValid:
            continue
        if isReportFile:
            yield Validation.error(
                codes='EDINET.EC0200E',
                msg=_("There is a file inside the XBRL directory that uses characters "
                      "other than those allowed (alphanumeric characters, '-' and '_'). "
                      "File: '%(path)s'. "
                      "Please change the filename to usable characters, and upload again."),
                path=str(path)
            )
        else:
            yield Validation.error(
                codes='EDINET.EC0121E',
                msg=_("There is a directory or file in '%(directory)s' that contains more "
                      "than 31 characters or uses characters other than those allowed "
                      "(alphanumeric characters, '-' and '_'). "
                      "Directory or filename: '%(basename)s'. "
                      "Please change the file name (or folder name) to within 31 characters and to usable "
                      "characters, and upload again."),
                directory=str(path.parent),
                basename=path.name,
            )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_manifest_preferredFilename(
        pluginData: ControllerPluginData,
        cntlr: Cntlr,
        fileSource: FileSource,
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

    EDINET.EC8008W: The file name of the report instance set in the manifest file
    does not conform to the rules.

    EDINET.EC8009W: The file name of the audit report instance set in the manifest file
    does not conform to the rules.
    """
    instances = pluginData.getManifestInstances()
    preferredFilenames: dict[Path, set[str]] = defaultdict(set)
    duplicateFilenames = defaultdict(set)
    for instance in instances:
        if len(instance.preferredFilename) == 0:
            yield Validation.error(
                codes='EDINET.EC5804E',
                msg=_("The instance file name is not set. "
                      "Set the instance name as the preferredFilename attribute value "
                      "of the instance element in the manifest file. (manifest: '%(manifest)s', id: %(id)s)"),
                manifest=str(instance.path),
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
                manifest=str(instance.path),
                id=instance.id,
            )
            continue

        reportFolderType = ReportFolderType.parse(instance.type)
        match = True if reportFolderType is None else any(
            pattern.fullmatch(preferredFilename.name)
            for pattern in reportFolderType.xbrlFilenamePatterns
        )
        if not match:
            if reportFolderType == ReportFolderType.AUDIT_DOC:
                yield Validation.warning(
                    codes='EDINET.EC8009W',
                    msg=_("The file name of the audit report instance set in the manifest "
                          "file does not conform to the rules. "
                          "File name: '%(file)s'. "
                          "Please set the file name of the corresponding audit report instance "
                          "according to the rules. Please correct the contents of the manifest file."),
                    file=preferredFilename.name,
                )
            else:
                yield Validation.warning(
                    codes='EDINET.EC8008W',
                    msg=_("The file name of the report instance set in the manifest "
                          "file does not comply with the regulations. "
                          "File name: '%(file)s'. "
                          "Please set the file name of the corresponding report instance "
                          "according to the rules. Please correct the contents of the manifest file."),
                    file=preferredFilename.name,
                )

        if instance.preferredFilename in preferredFilenames[instance.path]:
            duplicateFilenames[instance.path].add(instance.preferredFilename)
            continue
        preferredFilenames[instance.path].add(instance.preferredFilename)
    for path, filenames in duplicateFilenames.items():
        for filename in filenames:
            yield Validation.error(
                codes='EDINET.EC5806E',
                msg=_("The same instance file name is set multiple times. "
                      "File name: '%(preferredFilename)s'. "
                      "The preferredFilename attribute value of the instance "
                      "element in the manifest file must be unique within the "
                      "same file. (manifest: '%(manifest)s')"),
                manifest=str(path),
                preferredFilename=filename,
            )
