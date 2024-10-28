"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import json
import os
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Counter, cast

from arelle.packages import PackageUtils
from arelle.packages.report import ReportPackageConst as Const

if TYPE_CHECKING:
    from arelle.FileSource import FileSource


def getReportPackageTopLevelDirectory(filesource: FileSource) -> str | None:
    packageEntries = set(filesource.dir or [])
    potentialTopLevelReportDirs = {
        topLevelDir
        for topLevelDir in PackageUtils.getPackageTopLevelDirectories(filesource)
        if any(f"{topLevelDir}/{path}" in packageEntries for path in Const.REPORT_PACKAGE_PATHS)
    }
    if len(potentialTopLevelReportDirs) == 1:
        return next(iter(potentialTopLevelReportDirs))
    return None


def getReportPackageJsonFile(filesource: FileSource, stld: str | None) -> str | None:
    if not isinstance(filesource.fs, zipfile.ZipFile):
        return None
    # Match against original unsanitized file names and all their backslash glory.
    packageOriginalFileNames = [f.orig_filename for f in filesource.fs.infolist()]
    expectedFutureReportPackageJsonPath = Const.REPORT_PACKAGE_FILE
    expectedReportPackageJsonPath = f"{stld}/{Const.REPORT_PACKAGE_FILE}"
    futureReportPackageJsonPathPartialMatches = []
    reportPackageJsonPathPartialMatches = []
    for path in packageOriginalFileNames:
        if path.startswith(expectedFutureReportPackageJsonPath):
            futureReportPackageJsonPathPartialMatches.append(path)
        elif path.startswith(expectedReportPackageJsonPath):
            reportPackageJsonPathPartialMatches.append(path)

    jsonPath = None
    # Don't return content if there are duplicate entries or a directory with the same name as the json file.
    if len(futureReportPackageJsonPathPartialMatches) == 1:
        futureReportPackageJsonPath = futureReportPackageJsonPathPartialMatches[0]
        if futureReportPackageJsonPath == expectedFutureReportPackageJsonPath:
            jsonPath = expectedFutureReportPackageJsonPath
    elif len(futureReportPackageJsonPathPartialMatches) == 0:
        if len(reportPackageJsonPathPartialMatches) == 1:
            reportPackageJsonPath = reportPackageJsonPathPartialMatches[0]
            if reportPackageJsonPath == expectedReportPackageJsonPath:
                jsonPath = expectedReportPackageJsonPath
    return jsonPath


def getPackageJson(filesource: FileSource, selection: str | None) -> dict[str, Any] | None:
    if selection is None:
        return None
    initialSelection = filesource.selection
    initialUrl = filesource.url
    filesource.select(selection)
    fullJsonFilePath = cast(str, filesource.url)
    content = None
    encodings = ["utf-8", "utf-8-sig"]
    for encoding in encodings:
        try:
            with filesource.file(fullJsonFilePath, encoding=encoding)[0] as f:
                content = cast(dict[str, Any], json.load(f, object_pairs_hook=forbidDuplicateKeys))
                break
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError):
            continue
    # Restore selection and url including initial taxonomy packages with url, but no selection.
    filesource.selection = initialSelection
    filesource.url = initialUrl
    return content


def forbidDuplicateKeys(pairs: list[tuple[Any, Any]]) -> Any:
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key}")
        else:
            seen[key] = value
    return seen


def getAllReportEntries(filesource: FileSource, stld: str | None) -> list[ReportEntry] | None:
    if stld is None:
        return None
    if not isinstance(filesource.fs, zipfile.ZipFile):
        return None
    entries = [f.orig_filename for f in filesource.fs.infolist()]
    if not any(entry.startswith(f"{stld}/{Const.REPORTS_DIRECTORY}") for entry in entries):
        return None
    topReportEntries = []
    entriesBySubDir = defaultdict(list)
    for entry in entries:
        if entry.endswith("/"):
            continue
        path = PurePosixPath(entry)
        if path.suffix not in Const.REPORT_FILE_EXTENSIONS:
            continue
        if not (2 < len(path.parts) < 5):
            continue
        if not (path.parts[0] == stld and path.parts[1] == Const.REPORTS_DIRECTORY):
            continue
        if len(path.parts) == 3:
            topReportEntries.append(entry)
        else:
            entriesBySubDir[path.parts[2]].append(entry)
    assert isinstance(filesource.basefile, str)
    reportEntries = [ReportEntry(filesource.basefile, [entry]) for entry in topReportEntries]
    for entries in entriesBySubDir.values():
        if len(entries) == 1 or all(PurePosixPath(entry).suffix in Const.INLINE_REPORT_FILE_EXTENSIONS for entry in entries):
            reportEntries.append(ReportEntry(filesource.basefile, entries))
        else:
            reportEntries.extend(sorted(ReportEntry(filesource.basefile, [entry]) for entry in entries))
    return sorted(reportEntries)


@dataclass(frozen=True, order=True)
class ReportEntry:
    baseDir: str
    files: list[str]

    def __post_init__(self) -> None:
        if len(self.files) == 0:
            raise ValueError("Report entry must have at least one file")
        elif len(self.files) > 1 and any(
            PurePosixPath(f).suffix not in Const.INLINE_REPORT_FILE_EXTENSIONS for f in self.files
        ):
            raise ValueError("Non-inline report entries must be a single file")
        primaryDir = os.path.dirname(self.primary)
        if any(os.path.dirname(f) != primaryDir for f in self.files[1:]):
            raise ValueError("Report entry files must all be in the same directory")

    @property
    def primary(self) -> str:
        return self.files[0]

    @property
    def fullPathPrimary(self) -> str:
        return f"{self.baseDir}/{self.primary}"

    @property
    def isInline(self) -> bool:
        return PurePosixPath(self.primary).suffix in Const.INLINE_REPORT_FILE_EXTENSIONS

    @property
    def fullPathFiles(self) -> list[str]:
        return [f"{self.baseDir}/{f}" for f in self.files]

    @property
    def isTopLevel(self) -> bool:
        return len(PurePosixPath(self.primary).parts) == 3


class ReportPackage:
    def __init__(
        self,
        reportPackageZip: zipfile.ZipFile,
        stld: str | None,
        reportType: Const.ReportType | None,
        reportPackageJson: dict[str, Any] | None,
        reports: list[ReportEntry] | None,
    ) -> None:
        self._reportPackageZip = reportPackageZip
        self._stld = stld
        self._reportType = reportType
        self._reportPackageJson = reportPackageJson
        self._allReports = reports
        if self._allReports is None:
            self._reports = None
        else:
            reportTypeFileExtensions = reportType.reportFileExtensions if reportType is not None else frozenset()
            self._reports = [
                report
                for report in self._allReports
                if all(PurePosixPath(f).suffix in reportTypeFileExtensions for f in report.files)
            ]

    @staticmethod
    def fromFileSource(filesource: FileSource) -> ReportPackage | None:
        if not filesource.isOpen:
            filesource.open()
        if not isinstance(filesource.fs, zipfile.ZipFile):
            return None
        if not isinstance(filesource.basefile, str):
            raise ValueError(f"Report Package base file must be a string: {filesource.basefile}")
        reportType = Const.ReportType.fromExtension(Path(filesource.basefile).suffix)
        stld = getReportPackageTopLevelDirectory(filesource)
        reportPackageJsonFile = getReportPackageJsonFile(filesource, stld)
        reportPackageJson = None
        if reportPackageJsonFile:
            reportPackageJson = getPackageJson(filesource, reportPackageJsonFile)
        reports = getAllReportEntries(filesource, stld)
        if reportPackageJsonFile is None and reports is None:
            return None
        reportEntriesBySubDir = Counter(dir for report in reports or [] if not report.isTopLevel)
        if reports is not None and any(report.isTopLevel for report in reports):
            reports = [report for report in reports if report.isTopLevel]
        if any(subdirCount > 1 for subdirCount in reportEntriesBySubDir.values()):
            return None
        if reportType and reportType.isConstrained and len(reports or []) > 1:
            return None
        return ReportPackage(
            reportPackageZip=filesource.fs,
            stld=stld,
            reportType=reportType,
            reportPackageJson=reportPackageJson,
            reports=reports,
        )

    @property
    def documentInfo(self) -> Any:
        if self._reportPackageJson is None:
            return None
        return self._reportPackageJson.get("documentInfo")

    @property
    def documentType(self) -> Any:
        if isinstance(self.documentInfo, dict):
            return self.documentInfo.get("documentType")
        return None

    @property
    def stld(self) -> str | None:
        return self._stld

    @property
    def reportType(self) -> Const.ReportType | None:
        return self._reportType

    @property
    def allReports(self) -> list[ReportEntry] | None:
        return self._allReports

    @property
    def reports(self) -> list[ReportEntry] | None:
        return self._reports

    @property
    def reportPackageJson(self) -> dict[str, Any] | None:
        return self._reportPackageJson

    @property
    def reportPackageZip(self) -> zipfile.ZipFile:
        return self._reportPackageZip
