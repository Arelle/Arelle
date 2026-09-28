"""
See COPYRIGHT.md for copyright information.

UKSEF package validation rules (UKFRC9-UKFRC19).
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import PurePosixPath
from typing import Any, TYPE_CHECKING, cast

import tinycss2  # type: ignore[import-untyped]
from lxml import etree
from arelle import LeiUtil
from arelle import XbrlConst
from arelle.Cntlr import Cntlr
from arelle.typing import TypeGetText
from arelle.utils.validate.DetectScriptsInXhtml import containsScriptMarkers
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.FileSource import archiveFilenameParts, FileSource
from arelle.ValidateFilingText import validateGraphicHeaderType
from ...Const import AUTHORITY_UKFRC
from ...DisclosureSystems import UKSEF_ONLY_2025

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.packages.report.ReportPackage import ReportEntry
    from arelle.ModelObject import ModelObject
    from arelle.ValidateXbrl import ValidateXbrl
    from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


def _isCorrectExtension(report: ReportEntry) -> bool:
    """
    Determines if the file extension of the report's primary path is correct.

    Checks whether the file extension of the primary path in the provided report
    entry is either ".html" or ".xhtml". This function is used for validation of
    suitable file extensions for the report's primary resource.

    Args:
        report: The report entry containing the primary path to be validated.

    Returns:
        True if the file extension is either ".html" or ".xhtml", otherwise False.
    """
    return PurePosixPath(report.primary).suffix in (".html", ".xhtml")


def _cssImageUrls(tokens: Iterable[Any]) -> Iterable[str]:
    """
    Extracts and yields URLs from a collection of CSS tokens.

    This function processes a sequence of CSS tokens to extract URLs that are
    defined within `url()` functions or as direct URL values. It handles nested
    structures by recursively parsing child tokens or arguments if available.

    Args:
        tokens: An iterable sequence of CSS tokens, which may include URL tokens,
            function blocks, or other token types.

    Yields:
        Extracted URL strings from the provided CSS tokens.
    """
    for token in tokens:
        if isinstance(token, tinycss2.ast.URLToken):
            yield token.value.strip()

        elif isinstance(token, tinycss2.ast.FunctionBlock) and token.lower_name == "url":
            if token.arguments:
                yield "".join(
                    argument.value for argument in token.arguments
                    if hasattr(argument, "value")
                ).strip().strip("\"'")

        elif hasattr(token, "content"):
            yield from _cssImageUrls(token.content)

        elif hasattr(token, "arguments"):
            yield from _cssImageUrls(token.arguments)


def _cssDeclarationImageUrls(css: str, *, stylesheet: bool) -> Iterable[str]:
    """
    Extracts image URLs from CSS declarations or rules.

    This function parses a CSS string to extract URLs of images used in the
    CSS declarations or stylesheet rules. It supports parsing both inline CSS
    declarations and full CSS stylesheets.

    Args:
        css: The CSS content to parse.
        stylesheet: Indicates whether the provided CSS is a complete stylesheet (True)
                or a set of inline CSS declarations (False).

    Returns:
        An iterable of image URLs found in the CSS.
    """
    if stylesheet:
        rules = tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
        for rule in rules:
            if isinstance(rule, tinycss2.ast.QualifiedRule):
                declarations = tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True)
            elif isinstance(rule, tinycss2.ast.AtRule) and rule.content is not None:
                declarations = tinycss2.parse_declaration_list(rule.content, skip_comments=True, skip_whitespace=True)
            else:
                continue

            for declaration in declarations:
                if (isinstance(declaration, tinycss2.ast.Declaration)
                        and ("image" in declaration.lower_name or declaration.lower_name == "background")):
                    yield from _cssImageUrls(declaration.value)
    else:
        for declaration in tinycss2.parse_declaration_list(css, skip_comments=True, skip_whitespace=True):
            if (isinstance(declaration, tinycss2.ast.Declaration)
                    and ("image" in declaration.lower_name or declaration.lower_name == "background")):
                yield from _cssImageUrls(declaration.value)


def _iterImageUrls(modelXbrl: ModelXbrl) -> Iterable[tuple[ModelObject, str]]:
    """
    Generator function to iterate over image URLs found in an iXBRL document.

    This function yields tuples containing the element and the associated image
    URL for any `<img>` tags or CSS style attributes containing image references
    within the iXBRL document.

    Args:
        modelXbrl: An object representing the model of the iXBRL document. The model is
                expected to have an attribute `ixdsHtmlElements` which contains iterable
                HTML root elements.

    Yields:
        A tuple where the first element is the ModelObject representing the
        corresponding HTML or XML element, and the second element is the
        image URL as a string.
    """
    for htmlRoot in getattr(modelXbrl, "ixdsHtmlElements", ()):
        for element in htmlRoot.iter():
            localName = element.tag.rpartition("}")[2] if isinstance(element.tag, str) else ""
            if localName == "img":
                src = element.get("src", "").strip()
                if src:
                    yield element, src

            style = element.get("style")
            if style:
                for url in _cssDeclarationImageUrls(style, stylesheet=False):
                    if url:
                        yield element, url

            if localName == "style" and element.text:
                for url in _cssDeclarationImageUrls(element.text, stylesheet=True):
                    if url:
                        yield element, url


def _iterImageReferences(modelXbrl: ModelXbrl) -> Iterable[tuple[ModelObject, str, bool]]:
    """
    Generates an iterator over image references within a given model.

    This function operates on `ModelXbrl` instances to detect and yield
    references to images within the model. It processes each identified
    image URL, checks if it represents an inline Base64-encoded image,
    and yields the associated data.

    Args:
        modelXbrl: The model instance to analyze for image references.

    Yields:
        A tuple containing:
            - The element associated with the image.
            - The URL of the image as a string.
            - A boolean indicating whether the URL is a Base64-encoded inline
              image.
    """
    for element, url in _iterImageUrls(modelXbrl):
        yield element, url, url.lower().startswith("data:image") and ";base64," in url.lower()


def _iterScriptResources(fileSource: FileSource) -> Iterable[str]:
    """
    Iterates over script resources in the specified file source.

    This generator function examines file names in the provided file source and
    yields only those with file extensions considered as script resources (.js
    or .mjs). The comparison of file extensions is case-insensitive.

    Args:
        fileSource: The source containing files to be iterated.

    Yields:
        File names identified as script resources within the file source.
    """
    for fileName in fileSource.dir or ():
        if PurePosixPath(fileName).suffix.lower() in (".js", ".mjs"):
            yield fileName


def _archiveRelativePath(url: str) -> str | None:
    """
    Generates a relative path from an archive URL, if applicable.

    The function analyzes the given URL to extract parts relevant to an archive file
    and returns the relative path if the URL corresponds to an identifiable archive.
    If the URL does not match expected archive patterns, the function returns None.

    Args:
        url: The URL to analyze for potential archive-related information.

    Returns:
        The relative path extracted from the archive URL, or None if the URL does not
        correspond to an archive.
    """
    archiveParts = archiveFilenameParts(url)
    if archiveParts is not None:
        return archiveParts[1]

    return None


def _isInlineXbrlReport(fileSource: FileSource, report: ReportEntry) -> bool:
    """
    Determines if the given report is an Inline XBRL report by checking the file content.

    This function examines the XML structure of the provided file to identify if it contains
    any Inline XBRL (iXBRL) elements. The identification is based on matching the namespace of
    tags against known iXBRL namespaces. If an iXBRL tag is detected, the function confirms it
    as an Inline XBRL report.

    Args:
        fileSource: The source of the file to be examined, providing access to read the file.
        report: The report object containing the full path of the primary file to inspect.

    Returns:
        True if the report file is determined to be an Inline XBRL report, False otherwise.
    """
    with fileSource.file(report.fullPathPrimary, binary=True)[0] as reportFile:
        try:
            root = etree.fromstring(reportFile.read())
        except etree.XMLSyntaxError:
            return False

    return any(
        isinstance(element.tag, str)
        and element.tag.partition("}")[0].lstrip("{") in XbrlConst.ixbrlAll
        for element in root.iter()
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_disallowedReportPackageFileExtension(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC9: UKSEF report package MUST be submitted in a zipped report package (*.zip or *.xbri extensions only)
    """
    if val.authority != AUTHORITY_UKFRC:
        return

    fileSourceType = val.modelXbrl.fileSource.type
    if not pluginData.isUkfrsCorrectExtention(fileSourceType):
        yield Validation.error(
            codes="ESEF.UKFRC9.disallowedReportPackageFileExtension",
            msg=_("A UKSEF report package MUST be a zip archive with a .zip or .xbri extension."),
            fileSourceType=fileSourceType,
        )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=UKSEF_ONLY_2025
)
def rule_multipleReports(
        pluginData: PluginValidationDataExtension,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC10 and UKFRC11: A UKSEF report package MUST contain only one report
    in the "reports" directory.
    """
    reportPackage = fileSource.reportPackage
    if reportPackage is None or not reportPackage.reports:
        return

    if len(reportPackage.reports) > 1:
        yield Validation.error(
            codes="ESEF.UKFRC10.multipleReports",
            msg=_('A UKSEF report package MUST include only one report in the "reports" directory.'),
        )


@validation(
    hook=ValidationHook.FILESOURCE,
    disclosureSystems=UKSEF_ONLY_2025
)
def rule_noReportsPresent(
        pluginData: PluginValidationDataExtension,
        cntlr: Cntlr,
        fileSource: FileSource,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC10: The report package MUST include only one report in the “reports” directory.
    """
    reportPackage = fileSource.reportPackage
    if reportPackage is None or not pluginData.isUkfrsCorrectExtention(fileSource.type):
        return

    if (not reportPackage.reports
            or not _isCorrectExtension(reportPackage.reports[0])
            or not _isInlineXbrlReport(fileSource, reportPackage.reports[0])):
        yield Validation.error(
            codes="ESEF.UKFRC10.noReportsPresent",
            msg=_('A UKSEF report package MUST include one report in the "reports" directory.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_reportsSubdirectory(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC11: Subdirectories MUST NOT be used in the “reports” directory and
    MUST NOT contain more than one iXBRL document.
    """
    reportPackage = val.modelXbrl.fileSource.reportPackage
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isEsefTarget(val.modelXbrl)
            or reportPackage is None
            or not reportPackage.reports):
        return

    report = reportPackage.reports[0]
    if report and not report.isTopLevel:
        yield Validation.error(
            codes="ESEF.UKFRC11.reportsSubdirectory",
            msg=_('A UKSEF report package MUST NOT use subdirectories in the "reports" directory.'),
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_reportNotInline(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC12: The report MUST be XHTML tagged using the iXBRL format with a .html
    or .xhtml file extension only.
    """
    fileSource = val.modelXbrl.fileSource
    reportPackage = fileSource.reportPackage
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsCorrectExtention(fileSource.type)
            or reportPackage is None
            or not reportPackage.reports):
        return

    report = reportPackage.reports[0]
    if report and not _isCorrectExtension(report):
        yield Validation.error(
            codes="ESEF.UKFRC12.reportNotInline",
            msg=_(
                    "A UKSEF report MUST be XHTML tagged using the iXBRL format with "
                    "a .html or .xhtml file extension only: %(fileName)s"
                ),
                fileName=report.primary,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_executableCodePresent(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC13: Script-based iXBRL viewers MUST NOT be included either as part of
    iXBRL documents or as a separate resource.
    """
    fileSource = val.modelXbrl.fileSource
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsCorrectExtention(fileSource.type)
            or not pluginData.isEsefTarget(val.modelXbrl)):
        return

    for htmlRoot in getattr(val.modelXbrl, "ixdsHtmlElements", ()):
        for element in htmlRoot.iter():
            if not isinstance(element.tag, str):
                continue

            if containsScriptMarkers(element):
                yield Validation.error(
                    codes="ESEF.UKFRC13.executableCodePresent",
                    msg=_("Inline XBRL documents MUST NOT contain executable code: %(element)s"),
                    modelObject=element,
                    element=element.tag.rpartition("}")[2] if isinstance(element.tag, str) else element.tag,
                )

    for fileName in _iterScriptResources(fileSource):
        yield Validation.error(
            codes="ESEF.UKFRC13.executableCodePresent",
            msg=_("Script-based iXBRL viewers MUST NOT be included as a separate resource: %(fileName)s"),
            modelObject=val.modelXbrl,
            fileName=fileName,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc14(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC14: For tagged files, images can be provided either in the XHTML document
    as a base64 encoded string or be referenced as separate files in the package.
    The use of these two methods MUST NOT be combined.
    """
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isEsefTarget(val.modelXbrl)
            or not pluginData.isUkfrsCorrectExtention(val.modelXbrl.fileSource.type)):
        return

    fileSource = val.modelXbrl.fileSource
    embeddedImageFound = False
    referencedImageFound = False
    referenceElement = None
    outsidePackageImage: tuple[ModelObject, str] | None = None
    for element, imageUrl, isEmbedded in _iterImageReferences(val.modelXbrl):
        if isEmbedded:
            embeddedImageFound = True
        else:
            referencedImageFound = True
            referenceElement = element
            base = element.modelDocument.baseForElement(element)
            normalizedUrl = val.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(imageUrl, base)
            if (
                    not imageUrl.lower().startswith("data:")
                    and outsidePackageImage is None
                    and (
                        fileSource.fileSourceContainingFilepath(normalizedUrl) is not fileSource
                        or not fileSource.isInArchive(normalizedUrl, checkExistence=True)
                    )
            ):
                outsidePackageImage = (element, imageUrl)

    mixedImageReferenceFound = embeddedImageFound and referencedImageFound
    if outsidePackageImage is not None and not mixedImageReferenceFound:
        yield Validation.error(
            codes="ESEF.UKFRC14.imageOutsidePackage",
            msg=_("Images referenced by a UKSEF tagged file MUST be included in the report package: %(imageUrl)s"),
            modelObject=outsidePackageImage[0],
            imageUrl=outsidePackageImage[1],
        )

    if mixedImageReferenceFound:
        yield Validation.error(
            codes="ESEF.UKFRC14.mixedImageReference",
            msg=_(
                "A UKSEF tagged file MUST use either base64-encoded images embedded in the XHTML "
                "document or images referenced as separate files, but MUST NOT combine both methods."
            ),
            modelObject=referenceElement,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc15(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC15: If images are contained in separate files in the package, they MUST be in
    PNG, GIF, SVG or JPG/JPEG format. All the external referenced images MUST be placed
    in the same location within the zip package.
    """
    fileSource = val.modelXbrl.fileSource
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsCorrectExtention(fileSource.type)
            or not pluginData.isEsefTarget(val.modelXbrl)):
        return

    imageLocations: set[str] = set()
    for element, imageUrl in _iterImageUrls(val.modelXbrl):
        if imageUrl.lower().startswith("data:image"):
            continue

        base = element.modelDocument.baseForElement(element)
        normalizedUrl = val.modelXbrl.modelManager.cntlr.webCache.normalizeUrl(imageUrl, base)
        archiveRelativePath = _archiveRelativePath(normalizedUrl)
        if archiveRelativePath is None:
            continue

        imageLocation = str(PurePosixPath(archiveRelativePath).parent)
        imageLocations.add(imageLocation)
        imageExtension = PurePosixPath(archiveRelativePath).suffix.lower()
        if imageExtension not in {".png", ".gif", ".svg", ".jpg", ".jpeg"}:
            yield Validation.error(
                codes="ESEF.UKFRC15.imageFormatNotSupported",
                msg=_(
                    "Images referenced from a UKSEF XHTML document MUST be PNG, GIF, SVG or "
                    "JPG/JPEG files: %(fileName)s"
                ),
                modelObject=element,
                fileName=archiveRelativePath,
            )

        if imageExtension != ".svg":
            with fileSource.file(normalizedUrl, binary=True)[0] as imageFile:
                imageType = validateGraphicHeaderType(cast(bytes, imageFile.read()))

            if imageType and not (
                    imageType == imageExtension[1:]
                    or imageType == "jpg" and imageExtension == ".jpeg"
            ):
                yield Validation.error(
                    codes="ESEF.UKFRC15.imageDoesNotMatchItsFileExtension",
                    msg=_(
                        "The image type %(imageType)s does not match the file extension %(extension)s: "
                        "%(fileName)s"
                    ),
                    modelObject=element,
                    imageType=imageType,
                    extension=imageExtension,
                    fileName=archiveRelativePath,
                )

    if len(imageLocations) > 1:
        yield Validation.error(
            codes="ESEF.UKFRC15.mixedImageLocation",
            msg=_(
                "All externally referenced images in a UKSEF report package MUST be placed "
                "in the same location within the package. Found multiple locations: %(locations)s"
            ),
            locations=", ".join(imageLocations)
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_externalCssFileForSingleIXbrlDocument(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC16: CSS MUST be embedded in the XHTML document.
    """
    fileSource = val.modelXbrl.fileSource
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsCorrectExtention(fileSource.type)
            or not pluginData.isEsefTarget(val.modelXbrl)):
        return

    for htmlRoot in getattr(val.modelXbrl, "ixdsHtmlElements", ()):
        for element in htmlRoot.iter():
            if not isinstance(element.tag, str):
                continue

            localName = element.tag.rpartition("}")[2]
            if localName != "link":
                continue

            linkType = element.get("type", "").strip().lower()
            relValues = {value.lower() for value in element.get("rel", "").split()}
            if linkType == "text/css" or "stylesheet" in relValues:
                yield Validation.error(
                    codes="ESEF.UKFRC16.externalCssFileForSingleIXbrlDocument",
                    msg=_("CSS MUST be embedded in the XHTML document. Found external CSS link: %(fileName)s"),
                    modelObject=element,
                    fileName=element.get("href", "").strip()
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_reportPackageNameDoesNotFollowNamingConvention(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC17: For a report package, issuers are required to adopt a naming convention
    which matches {base}-{date}.zip or {base}-{date}.xbri, whereby:
    *	The {base} component of the filename shall indicate the LEI of the issuer
    *	The {date} component of the filename should indicate the accounting reference date.
        The {date} component should follow the YYYY-MM-DD format.
    E.g. 213800YWQOYL4VQODV50-2022-12-31.zip.
    """
    fileSource = val.modelXbrl.fileSource
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isEsefTarget(val.modelXbrl)):
        return

    packagePath = fileSource.basefile or fileSource.url
    packageName = PurePosixPath(str(packagePath)).name
    packageStem = PurePosixPath(packageName).stem
    packageExtension = PurePosixPath(packageName).suffix

    try:
        reportDate = date.fromisoformat(packageStem[packageStem.find("-") + 1:])
    except ValueError:
        reportDate = None

    parts = packageStem.rsplit("-", 3)
    if (
            not pluginData.isUkfrsCorrectExtention(packageExtension)
            or len(parts) != 4
            or LeiUtil.checkLei(parts[0]) != LeiUtil.LEI_VALID
            or not reportDate
    ):
        yield Validation.error(
            codes="ESEF.UKFRC17.reportPackageNameDoesNotFollowNamingConvention",
            msg=_(
                "A UKSEF report package filename MUST match {base}-{date}.zip or {base}-{date}.xbri. "
                "The {base} component of the filename shall indicate the LEI of the issuer."
                "The {date} component should follow the YYYY-MM-DD format: %(packageName)s"
            ),
            packageName=packageName,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_reportFileNameDoesNotFollowNamingConvention(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC18: For a tagged xHTML file within a report package, issuers are required to
    adopt a naming convention which matches {base}-{date}.html or .xhtml whereby:
    *	The {base} component of the filename shall indicate the LEI of the issuer
    *	The {date} component of the filename should indicate the accounting reference date.
        The {date} component should follow the YYYY-MM-DD format.
    E.g. 213800YWQOYL4VQODV50-2022-12-31.html
    The filename MAY also end with "-T01"
    Note: This differs from the ESEF requirement which specifies a language component as well
    (hence the ESEF package name errors in all cases)
    """
    fileSource = val.modelXbrl.fileSource
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsCorrectExtention(fileSource.type)
            or not pluginData.isEsefTarget(val.modelXbrl)):
        return

    reportPackage = fileSource.reportPackage
    if (reportPackage is None
            or reportPackage.reports is None
            or len(reportPackage.reports) > 1):
        return

    for report in reportPackage.reports:
        reportName = PurePosixPath(report.primary).name
        reportStem = PurePosixPath(reportName).stem
        if reportStem.endswith("-T01"):
            reportStem = reportStem[:-4]

        try:
            reportDate = date.fromisoformat(reportStem[reportStem.find("-") + 1:])
        except ValueError:
            reportDate = None

        parts = reportStem.rsplit("-", 3)

        if (
            not _isCorrectExtension(report)
            or len(parts) != 4
            or LeiUtil.checkLei(parts[0]) != LeiUtil.LEI_VALID
            or not reportDate
        ):
            yield Validation.error(
                codes="ESEF.UKFRC18.reportFileNameDoesNotFollowNamingConvention",
                msg=_(
                    "A UKSEF XHTML report filename MUST match {base}-{date}.html or {base}-{date}.xhtml. "
                    "The {base} component of the filename shall indicate the LEI of the issuer."
                    "The {date} component should follow the YYYY-MM-DD format, optionally followed by -T01: %(fileName)s"
                ),
                modelObject=val.modelXbrl,
                fileName=reportName,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_spaceInFilePath(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC19: Any other file present in a report package MUST NOT include spaces in the filename.
    """
    fileSource = val.modelXbrl.fileSource
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsCorrectExtention(fileSource.type)
            or not pluginData.isEsefTarget(val.modelXbrl)
            or not fileSource.dir):
        return

    curruptedFileNames = [fileName for fileName in fileSource.dir if " " in fileName]

    if curruptedFileNames:
        yield Validation.error(
            codes="ESEF.UKFRC19.spaceInFilePath",
            msg=_(
                "Any other file present in a UKSEF report package MUST NOT include spaces in the filename: "
                "%(fileName)s"
                ),
            fileName=", ".join(curruptedFileNames),
        )
