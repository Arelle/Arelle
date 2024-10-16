"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

import json
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

from arelle.packages import PackageUtils
from arelle.packages.report import ReportPackageConst as Const

if TYPE_CHECKING:
    from arelle.FileSource import FileSource


def _getReportPackageTopLevelDirectory(filesource: FileSource) -> str | None:
    packageEntries = set(filesource.dir or [])
    potentialTopLevelReportDirs = {
        topLevelDir
        for topLevelDir in PackageUtils.getPackageTopLevelDirectories(filesource)
        if any(f"{topLevelDir}/{path}" in packageEntries for path in Const.REPORT_PACKAGE_PATHS)
    }
    if len(potentialTopLevelReportDirs) == 1:
        return next(iter(potentialTopLevelReportDirs))
    return None


def _getReportPackageJson(filesource: FileSource, stld: str | None) -> dict[str, Any] | None:
    packageJsonPath = f"{stld}/{Const.REPORT_PACKAGE_FILE}"
    if stld is None or packageJsonPath not in (filesource.dir or []):
        return None
    initialSelection = filesource.selection
    initialUrl = filesource.url
    try:
        filesource.select(packageJsonPath)
        fullPackageJsonPath = cast(str, filesource.url)
        with filesource.file(fullPackageJsonPath, binary=True)[0] as rpj:
            return cast(dict[str, Any], json.load(rpj))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError):
        return None
    finally:
        filesource.selection = initialSelection
        filesource.url = initialUrl


def _getAllReportEntries(filesource: FileSource, stld: str | None) -> list[ReportEntry] | None:
    if stld is None:
        return None
    entries = filesource.dir or []
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
    reportEntries = []
    assert isinstance(filesource.basefile, str)
    if topReportEntries:
        reportEntries.extend([ReportEntry(filesource.basefile, [entry]) for entry in topReportEntries])
    else:
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
        elif len(self.files) > 1 and any(PurePosixPath(f).suffix not in Const.INLINE_REPORT_FILE_EXTENSIONS for f in self.files):
            raise ValueError("Non-inline report entries must be a single file")

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

class ReportPackage:
    def __init__(
        self,
        reportPackageZip: zipfile.ZipFile,
        stld: str,
        reportType: Const.ReportType,
        reportPackageJson: dict[str, Any],
        reports: list[ReportEntry],
    ) -> None:
        self._reportPackageZip = reportPackageZip
        self._stld = stld
        self._reportType = reportType
        self._reportPackageJson = reportPackageJson
        self._allReports = reports
        self._reports = [
            report for report in self._allReports
            if all(PurePosixPath(f).suffix in reportType.reportFileExtensions for f in report.files)
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
        if reportType is None:
            return None
        stld = _getReportPackageTopLevelDirectory(filesource)
        if stld is None:
            return None
        reportPackageJson = _getReportPackageJson(filesource, stld)
        reports = _getAllReportEntries(filesource, stld)
        if reportPackageJson is None and reports is None:
            return None
        return ReportPackage(
            reportPackageZip=filesource.fs,
            stld=stld,
            reportType=reportType,
            reportPackageJson=reportPackageJson or {},
            reports=reports or [],
        )

    @property
    def documentType(self) -> Any:
        if self._reportPackageJson is None:
            return None
        return self._reportPackageJson.get("documentInfo", {}).get("documentType")

    @property
    def reportType(self) -> Const.ReportType | None:
        return self._reportType

    @property
    def allReports(self) -> list[ReportEntry]:
        return self._allReports

    @property
    def reports(self) -> list[ReportEntry]:
        return self._reports

    @property
    def reportPackageJson(self) -> dict[str, Any] | None:
        return self._reportPackageJson

    @property
    def reportPackageZip(self) -> zipfile.ZipFile | None:
        return self._reportPackageZip
