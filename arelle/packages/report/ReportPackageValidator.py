"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Counter, cast

from arelle.packages import PackageValidation
from arelle.packages.PackageType import PackageType
from arelle.packages.report import ReportPackageConst as Const
from arelle.packages.report.ReportPackage import (
    forbidDuplicateKeys,
    getAllReportEntries,
    getReportPackageJson,
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
        for error in self._validatePackageJson():
            yield error
            return
        yield from self._validateReports()
        return

    def _validatePackageJson(self) -> Generator[Validation, None, None]:
        reportPackageJson = getReportPackageJson(self._filesource, self._reportPackageJsonFile)
        if reportPackageJson is None:
            if self._reportPackageJsonFile in (self._filesource.dir or []):
                yield Validation.error(
                    "rpe:invalidJSON",
                    _("Report package JSON file must be a valid JSON file, per RFC 8259."),
                )
            elif self._reportType in {
                Const.ReportType.NON_INLINE_XBRL_REPORT_PACKAGE,
                Const.ReportType.INLINE_XBRL_REPORT_PACKAGE,
            }:
                yield Validation.error(
                    "rpe:documentTypeFileExtensionMismatch",
                    _("%(reportType)s report package requires a report package JSON file"),
                    reportType="Inline" if self._reportType == Const.ReportType.INLINE_XBRL_REPORT_PACKAGE else "Non-Inline",
                )
            return
        documentInfo = reportPackageJson.get("documentInfo")
        if not isinstance(documentInfo, dict):
            yield Validation.error(
                "rpe:invalidJSONStructure",
                _("Report package 'documentInfo' must resolve to a JSON object: %(documentInfo)s"),
                documentInfo=documentInfo,
            )
            return
        documentType = documentInfo.get("documentType")
        if not isinstance(documentType, str):
            yield Validation.error(
                "rpe:invalidJSONStructure",
                _("Report package type 'documentInfo.documentType' must resolve to a JSON string: %(documentType)s"),
                documentType=documentType,
            )
            return
        if documentType not in Const.SUPPORTED_DOCUMENT_TYPES or self._stld is None:
            yield Validation.error(
                "rpe:unsupportedReportPackageVersion",
                _("Report package document type '%(documentType)s' is not supported."),
                documentType=documentType,
            )
            return
        validDocumentTypeForFileExtension = True
        if documentType == Const.INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE:
            validDocumentTypeForFileExtension = self._reportType == Const.ReportType.INLINE_XBRL_REPORT_PACKAGE
        elif documentType == Const.NON_INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE:
            validDocumentTypeForFileExtension = self._reportType == Const.ReportType.NON_INLINE_XBRL_REPORT_PACKAGE
        elif documentType == Const.UNCONSTRAINED_REPORT_PACKAGE_DOCUMENT_TYPE:
            validDocumentTypeForFileExtension = self._reportType == Const.ReportType.UNCONSTRAINED_REPORT_PACKAGE
        else:
            yield Validation.error(
                "rpe:unsupportedReportPackageVersion",
                _("Report package document type '%(documentType)s' is not supported."),
                documentType=documentType,
            )
            return
        if not validDocumentTypeForFileExtension:
            yield Validation.error(
                "rpe:documentTypeFileExtensionMismatch",
                _(
                    "Report package document type '%(documentType)s' does not match the file extension: %(reportType)s"
                ),
                documentType=documentType,
                reportType=self._reportType.value if self._reportType is not None else None,
            )
            return

    def _validateReports(self) -> Generator[Validation, None, None]:
        reportEntries = getAllReportEntries(self._filesource, self._stld)
        filesourceFiles = self._filesource.dir or []
        topLevelDir = f"{self._stld}/" if self._stld else ""
        reportsDirExist = any(entry.startswith(f"{topLevelDir}/reports") for entry in filesourceFiles)
        reportPackageJsonFileExist = f"{self._stld}/{Const.REPORT_PACKAGE_FILE}" in filesourceFiles
        if not reportsDirExist and not reportPackageJsonFileExist:
            return
        if self._reportType is not None:
            if not any(entry.startswith(f"{self._stld}/reports") for entry in self._filesource.dir or []):
                yield Validation.error(
                    "rpe:missingReportsDirectory",
                    _("Report package must contain a reports directory"),
                )
                return
            if not reportEntries:
                yield Validation.error(
                    "rpe:missingReport",
                    _("Report package must contain at least one report"),
                )
                return
            if len(reportEntries) > 1 and not any(report.isTopLevel for report in reportEntries):
                byBaseDir = Counter(report.baseDir for report in reportEntries)
                if byBaseDir:
                    yield Validation.error(
                        "rpe:multipleReportsInSubdirectory",
                        _("Report package must contain only one report"),
                    )
                    return
            if self._reportType == Const.ReportType.NON_INLINE_XBRL_REPORT_PACKAGE:
                if len(reportEntries) > 1:
                    yield Validation.error(
                        "rpe:multipleReports",
                        _("Non-inline XBRL report package must contain only one report"),
                    )
                    return
                if any(PurePosixPath(entry.primary).suffix not in Const.NON_INLINE_REPORT_FILE_EXTENSIONS for entry in reportEntries):
                    yield Validation.error(
                        "rpe:incorrectReportType",
                        _("Non-inline XBRL report package must contain only non-inline XBRL reports"),
                    )
                    return
                for report in reportEntries or []:
                    if PurePosixPath(report.primary).suffix == Const.JSON_REPORT_FILE_EXTENSION:
                        initialSelection = self._filesource.selection
                        initialUrl = self._filesource.url
                        self._filesource.select(report.primary)
                        fullPackageJsonPath = cast(str, self._filesource.url)
                        encodings = ["utf-8", "utf-8-sig"]
                        reportContent = None
                        for encoding in encodings:
                            with self._filesource.file(fullPackageJsonPath, encoding=encoding)[0] as f:
                                try:
                                    reportContent = json.load(f, object_pairs_hook=forbidDuplicateKeys)
                                    break
                                except (ValueError, json.JSONDecodeError):
                                    continue
                        self._filesource.selection = initialSelection
                        self._filesource.url = initialUrl
                        if reportContent is None:
                            yield Validation.error(
                                "rpe:invalidJSON",
                                _("Non-inline XBRL report package must contain only valid JSON reports"),
                            )
                            return
                        reportDocumentInfo = reportContent.get("documentInfo")
                        if not isinstance(reportDocumentInfo, dict):
                            yield Validation.error(
                                "rpe:invalidJSONStructure",
                                _("Report package 'documentInfo' must resolve to a JSON object: %(documentInfo)s"),
                                documentInfo=reportDocumentInfo,
                            )
                            return
                        reportDocumentType = reportDocumentInfo.get("documentType")
                        if not isinstance(reportDocumentType, str):
                            yield Validation.error(
                                "rpe:invalidJSONStructure",
                                _("Report package type 'documentInfo.documentType' must resolve to a JSON string: %(documentType)s"),
                                documentType=reportDocumentType,
                            )
                            return

            elif self._reportType == Const.ReportType.INLINE_XBRL_REPORT_PACKAGE:
                if len(reportEntries) > 1:
                    yield Validation.error(
                        "rpe:multipleReports",
                        _("Inline XBRL report package must contain only one report"),
                    )
                    return
                if any(PurePosixPath(entry.primary).suffix not in Const.INLINE_REPORT_FILE_EXTENSIONS for entry in reportEntries):
                    yield Validation.error(
                        "rpe:incorrectReportType",
                        _("Inline XBRL report package must contain only inline XBRL reports"),
                    )
                    return
        return
