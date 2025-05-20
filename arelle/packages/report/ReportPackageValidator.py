"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Generator
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from arelle.packages import PackageValidation
from arelle.packages.PackageType import PackageType
from arelle.packages.report import ReportPackageConst as Const
from arelle.packages.report.ReportPackage import (
    getAllReportEntries,
    getPackageJson,
    getReportPackageJsonFile,
    getReportPackageTopLevelDirectory,
)
from arelle.typing import TypeGetText
from arelle.utils.validate.Validation import Validation

if TYPE_CHECKING:
    from arelle.FileSource import FileSource

_: TypeGetText


REPORT_PACKAGE_TYPE = PackageType("Report", "rpe")

REPORT_PACKAGE_ABORTING_VALIDATIONS = (
    PackageValidation.validatePackageZipFormat,
    PackageValidation.validateZipFileSeparators,
    PackageValidation.validatePackageNotEncrypted,
    PackageValidation.validateTopLevelDirectories,
    PackageValidation.validateDuplicateEntries,
    PackageValidation.validateConflictingEntries,
    PackageValidation.validateEntries,
)

REPORT_PACKAGE_NON_ABORTING_VALIDATIONS = (PackageValidation.validateMetadataDirectory,)


class ReportPackageValidator:
    def __init__(self, filesource: FileSource) -> None:
        self._filesource = filesource
        assert isinstance(self._filesource.basefile, str)
        self._reportType = Const.ReportType.fromExtension(Path(self._filesource.basefile).suffix)
        self._stld = getReportPackageTopLevelDirectory(self._filesource)
        self._reportPackageJsonFile = getReportPackageJsonFile(self._filesource, self._stld)

    def validate(self) -> Generator[Validation, None, None]:
        if self._filesource.reportPackage is not None and self._filesource.reportPackage.reportType is None:
            yield Validation.error(
                "rpe:unsupportedFileExtension",
                _("Report package has unsupported file extension."),
            )
            return
        for validation in REPORT_PACKAGE_ABORTING_VALIDATIONS:
            if error := validation(REPORT_PACKAGE_TYPE, self._filesource):
                yield error
                return
        if (error := self._validatePackageJson()) or (error := self._validateReports()):
            yield error
        return

    def _validatePackageJson(self) -> Validation | None:
        reportPackageJson = getPackageJson(self._filesource, self._reportPackageJsonFile)
        if reportPackageJson is None:
            if self._reportPackageJsonFile in (self._filesource.dir or []):
                return Validation.error(
                    "rpe:invalidJSON",
                    _("Report package JSON file must be a valid JSON file, per RFC 8259."),
                )
            elif self._reportType in {
                Const.ReportType.NON_INLINE_XBRL_REPORT_PACKAGE,
                Const.ReportType.INLINE_XBRL_REPORT_PACKAGE,
            }:
                return Validation.error(
                    "rpe:documentTypeFileExtensionMismatch",
                    _("%(reportType)s report package requires a report package JSON file"),
                    reportType="Inline"
                    if self._reportType == Const.ReportType.INLINE_XBRL_REPORT_PACKAGE
                    else "Non-Inline",
                )
            return None
        documentInfo = reportPackageJson.get("documentInfo")
        if not isinstance(documentInfo, dict):
            return Validation.error(
                "rpe:invalidJSONStructure",
                _("Report package 'documentInfo' must resolve to a JSON object: %(documentInfo)s"),
                documentInfo=documentInfo,
            )
        documentType = documentInfo.get("documentType")
        if not isinstance(documentType, str):
            return Validation.error(
                "rpe:invalidJSONStructure",
                _("Report package type 'documentInfo.documentType' must resolve to a JSON string: %(documentType)s"),
                documentType=documentType,
            )
        if documentType not in Const.SUPPORTED_DOCUMENT_TYPES or self._stld is None:
            return Validation.error(
                "rpe:unsupportedReportPackageVersion",
                _("Report package document type '%(documentType)s' is not supported."),
                documentType=documentType,
            )
        validDocumentTypeForFileExtension = True
        if documentType == Const.INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE:
            validDocumentTypeForFileExtension = self._reportType == Const.ReportType.INLINE_XBRL_REPORT_PACKAGE
        elif documentType == Const.NON_INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE:
            validDocumentTypeForFileExtension = self._reportType == Const.ReportType.NON_INLINE_XBRL_REPORT_PACKAGE
        elif documentType == Const.UNCONSTRAINED_REPORT_PACKAGE_DOCUMENT_TYPE:
            validDocumentTypeForFileExtension = self._reportType == Const.ReportType.UNCONSTRAINED_REPORT_PACKAGE
        else:
            return Validation.error(
                "rpe:unsupportedReportPackageVersion",
                _("Report package document type '%(documentType)s' is not supported."),
                documentType=documentType,
            )
        if not validDocumentTypeForFileExtension:
            return Validation.error(
                "rpe:documentTypeFileExtensionMismatch",
                _("Report package document type '%(documentType)s' does not match the file extension: %(reportType)s"),
                documentType=documentType,
                reportType=self._reportType.value if self._reportType is not None else None,
            )
        return None

    def _validateReports(self) -> Validation | None:
        reportEntries = getAllReportEntries(self._filesource, self._stld)
        filesourceFiles = self._filesource.dir or []
        topLevelDir = f"{self._stld}/" if self._stld else ""
        reportsDirExist = any(entry.startswith(f"{topLevelDir}/reports") for entry in filesourceFiles)
        reportPackageJsonFileExist = f"{self._stld}/{Const.REPORT_PACKAGE_FILE}" in filesourceFiles
        if not reportsDirExist and not reportPackageJsonFileExist:
            return None
        if self._reportType is not None:
            if not any(entry.startswith(f"{self._stld}/reports") for entry in self._filesource.dir or []):
                return Validation.error(
                    "rpe:missingReportsDirectory",
                    _("Report package must contain a reports directory"),
                )
            if not reportEntries:
                return Validation.error(
                    "rpe:missingReport",
                    _("Report package must contain at least one report"),
                )
            if len(reportEntries) > 1 and not any(report.isTopLevel for report in reportEntries):
                reportEntriesBySubDir = Counter(report.dir for report in reportEntries or [] if not report.isTopLevel)
                if any(subdirCount > 1 for subdirCount in reportEntriesBySubDir.values()):
                    return Validation.error(
                        "rpe:multipleReportsInSubdirectory",
                        _("Report package must contain only one report"),
                    )
            if self._reportType == Const.ReportType.NON_INLINE_XBRL_REPORT_PACKAGE:
                if len(reportEntries) > 1:
                    return Validation.error(
                        "rpe:multipleReports",
                        _("Non-inline XBRL report package must contain only one report"),
                    )
                if any(
                    PurePosixPath(entry.primary).suffix not in Const.NON_INLINE_REPORT_FILE_EXTENSIONS
                    for entry in reportEntries
                ):
                    return Validation.error(
                        "rpe:incorrectReportType",
                        _("Non-inline XBRL report package must contain only non-inline XBRL reports"),
                    )
                for report in reportEntries or []:
                    if PurePosixPath(report.primary).suffix == Const.JSON_REPORT_FILE_EXTENSION:
                        reportContent = getPackageJson(self._filesource, report.primary)
                        if reportContent is None:
                            return Validation.error(
                                "rpe:invalidJSON",
                                _("Non-inline XBRL report package must contain only valid JSON reports"),
                            )
                        reportDocumentInfo = reportContent.get("documentInfo")
                        if not isinstance(reportDocumentInfo, dict):
                            return Validation.error(
                                "rpe:invalidJSONStructure",
                                _("Report package 'documentInfo' must resolve to a JSON object: %(documentInfo)s"),
                                documentInfo=reportDocumentInfo,
                            )
                        reportDocumentType = reportDocumentInfo.get("documentType")
                        if not isinstance(reportDocumentType, str):
                            return Validation.error(
                                "rpe:invalidJSONStructure",
                                _("Report package type 'documentInfo.documentType' must resolve to a JSON string: %(documentType)s"),
                                documentType=reportDocumentType,
                            )

            elif self._reportType == Const.ReportType.INLINE_XBRL_REPORT_PACKAGE:
                if len(reportEntries) > 1:
                    return Validation.error(
                        "rpe:multipleReports",
                        _("Inline XBRL report package must contain only one report"),
                    )
                if any(
                    PurePosixPath(entry.primary).suffix not in Const.INLINE_REPORT_FILE_EXTENSIONS
                    for entry in reportEntries
                ):
                    return Validation.error(
                        "rpe:incorrectReportType",
                        _("Inline XBRL report package must contain only inline XBRL reports"),
                    )
        return None
