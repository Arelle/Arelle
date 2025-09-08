"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, TYPE_CHECKING

import regex

from arelle import UrlUtil
from arelle.Cntlr import Cntlr
from arelle.FileSource import FileSource
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from .. import Constants
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..ReportFolderType import ReportFolderType, HTML_EXTENSIONS, IMAGE_EXTENSIONS
from ..PluginValidationDataExtension import PluginValidationDataExtension

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

FILENAME_STEM_PATTERN = re.compile(r'[a-zA-Z0-9_-]*')

PATTERN_CODE = r'(?P<code>[A-Za-z\d]*)'
PATTERN_CONSOLIDATED = r'(?P<consolidated>c|n)'
PATTERN_COUNT = r'(?P<count>\d{2})'
PATTERN_DATE1 = r'(?P<year1>\d{4})-(?P<month1>\d{2})-(?P<day1>\d{2})'
PATTERN_DATE2 = r'(?P<year2>\d{4})-(?P<month2>\d{2})-(?P<day2>\d{2})'
PATTERN_FORM = r'(?P<form>\d{6})'
PATTERN_LINKBASE = r'(?P<linkbase>lab|lab-en|gla|pre|def|cal)'
PATTERN_MAIN = r'(?P<main>\d{7})'
PATTERN_NAME = r'(?P<name>[a-z]{6})'
PATTERN_ORDINANCE = r'(?P<ordinance>[a-z]*)'
PATTERN_PERIOD = r'(?P<period>c|p)'  # TODO: Have only seen "c" in sample/public filings, assuming "p" for previous.
PATTERN_REPORT = r'(?P<report>[a-z]*)'
PATTERN_REPORT_SERIAL = r'(?P<report_serial>\d{3})'
PATTERN_SERIAL = r'(?P<serial>\d{3})'

PATTERN_AUDIT_REPORT_PREFIX = rf'jpaud-{PATTERN_REPORT}-{PATTERN_PERIOD}{PATTERN_CONSOLIDATED}'
PATTERN_REPORT_PREFIX = rf'jp{PATTERN_ORDINANCE}{PATTERN_FORM}-{PATTERN_REPORT}'
PATTERN_SUFFIX = rf'{PATTERN_REPORT_SERIAL}_{PATTERN_CODE}-{PATTERN_SERIAL}_{PATTERN_DATE1}_{PATTERN_COUNT}_{PATTERN_DATE2}'

PATTERNS = list(regex.compile(p) for p in (
    # Schema file for report
    # Example: jpcrp050300-esr-001_X99007-000_2025-04-10_01_2025-04-10.xsd
    rf'{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}.xsd',
    # Schema file for audit report
    # Example: jpaud-aar-cn-001_X99001-000_2025-03-31_01_2025-06-28.xsd
    rf'{PATTERN_AUDIT_REPORT_PREFIX}-{PATTERN_SUFFIX}.xsd',
    # Linkbase file for report
    # Example: jpcrp020000-srs-001_X99001-000_2025-03-31_01_2025-11-20_cal.xml
    rf'{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}_{PATTERN_LINKBASE}.xml',
    # Linkbase file for audit report
    # Example: jpaud-qrr-cc-001_X99001-000_2025-03-31_01_2025-11-20_pre.xml
    rf'{PATTERN_AUDIT_REPORT_PREFIX}-{PATTERN_SUFFIX}_{PATTERN_LINKBASE}.xml',
    # Cover page file for report
    # Example: 0000000_header_jpcrp020000-srs-001_X99001-000_2025-03-31_01_2025-11-20_ixbrl.htm
    rf'{Constants.COVER_PAGE_FILENAME_PREFIX}{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}_ixbrl.htm',
    # Main file for report
    # Example: 0205020_honbun_jpcrp020000-srs-001_X99001-000_2025-03-31_01_2025-11-20_ixbrl.htm
    rf'{PATTERN_MAIN}_{PATTERN_NAME}_{PATTERN_REPORT_PREFIX}-{PATTERN_SUFFIX}_ixbrl.htm',
    # Main file for audit report
    # Example: jpaud-qrr-cc-001_X99001-000_2025-03-31_01_2025-11-20_pre.xml
    rf'{PATTERN_AUDIT_REPORT_PREFIX}-{PATTERN_SUFFIX}_ixbrl.htm',
))

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
    uploadContents = pluginData.getUploadContents(fileSource)
    for path, pathInfo in uploadContents.uploadPaths.items():
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
    for path in uploadFilepaths:
        if path.suffix:
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
    uploadContents = pluginData.getUploadContents(fileSource)
    for path, pathInfo in uploadContents.uploadPaths.items():
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
    EDINET.EC0132E: Store the manifest file directly under the relevant folder.
    """
    uploadContents = pluginData.getUploadContents(fileSource)
    for reportFolderType, paths in uploadContents.reports.items():
        if reportFolderType.isAttachment:
            continue
        if reportFolderType.manifestPath not in paths:
            yield Validation.error(
                codes='EDINET.EC0132E',
                msg=_("'%(expectedManifestName)s' does not exist in '%(expectedManifestDirectory)s'. "
                      "Please store the manifest file (or cover file) directly under the relevant folder and upload it again. "),
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
    pattern = re.compile(r'^\d{7}')
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
    uploadContents = pluginData.getUploadContents(fileSource)
    for path, pathInfo in uploadContents.uploadPaths.items():
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
    uploadContents = pluginData.getUploadContents(fileSource)
    directories = defaultdict(list)
    for path in uploadContents.sortedPaths:
        pathInfo = uploadContents.uploadPaths[path]
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
    uploadContents = pluginData.getUploadContents(fileSource)
    for path, pathInfo in uploadContents.uploadPaths.items():
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
    EDINET.EC0349E: An unexpected directory or file exists in the XBRL directory.
    Only PublicDoc, PrivateDoc, or AuditDoc directories may exist beneath the XBRL directory.
    """
    uploadContent = pluginData.getUploadContents(fileSource)
    xbrlDirectoryPath = Path('XBRL')
    allowedPaths = {p.xbrlDirectory for p in (
        ReportFolderType.AUDIT_DOC,
        ReportFolderType.PRIVATE_DOC,
        ReportFolderType.PUBLIC_DOC,
    )}
    for path, pathInfo in uploadContent.uploadPaths.items():
        if path.parent != xbrlDirectoryPath:
            continue
        if path not in allowedPaths:
            if not any(pattern.fullmatch(path.name) for pattern in PATTERNS):
                yield Validation.error(
                    codes='EDINET.EC0349E',
                    msg=_("An unexpected directory or file exists in the XBRL directory. "
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
    uploadContent = pluginData.getUploadContents(fileSource)
    for path, pathInfo in uploadContent.uploadPaths.items():
        if (
            pathInfo.isDirectory or
            pathInfo.isCorrection or
            pathInfo.isSubdirectory or
            pathInfo.isAttachment or
            pathInfo.reportFolderType is None or
            any(path == t.manifestPath for t in ReportFolderType)
        ):
            continue
        if not any(pattern.fullmatch(path.name) for pattern in PATTERNS):
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
    EDINET.EC1007E: The URI in the HTML specifies a URL or absolute path.
    EDINET.EC1013E: The URI in the HTML specifies a path not under a subdirectory.
    EDINET.EC1014E: The URI in the HTML specifies a path to a file that doesn't exist.
    """
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
        path = Path(uriReference.attributeValue)
        if len(path.parts) < 2:
            yield Validation.error(
                codes='EDINET.EC1013E',
                msg=_("The URI in the HTML specifies a path not under a subdirectory. "
                      "File name: '%(file)s' (line %(line)s). "
                      "Please move the referenced file into a subfolder, or correct the URI."),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue
        fullPath = Path(uriReference.document.uri).parent / path
        if not val.modelXbrl.fileSource.exists(str(fullPath)):
            yield Validation.error(
                codes='EDINET.EC1014E',
                msg=_("The URI in the HTML specifies a path to a file that doesn't exist. "
                      "File name: '%(file)s' (line %(line)s). "
                      "Please update the URI to reference a file."),
                file=uriReference.document.basename,
                line=uriReference.element.sourceline,
                modelObject=uriReference.element,
            )
            continue


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
    uploadContents = pluginData.getUploadContents(fileSource)
    existingSubdirectoryFilepaths = {
        path
        for path, pathInfo in uploadContents.uploadPaths.items()
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
    for path, pathInfo in pluginData.getUploadContents(fileSource).uploadPaths.items():
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
