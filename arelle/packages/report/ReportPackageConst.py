"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from enum import Enum

from arelle.packages.PackageConst import META_INF_DIRECTORY

INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE = "https://xbrl.org/report-package/2023/xbri"
NON_INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE = "https://xbrl.org/report-package/2023/xbr"
UNCONSTRAINED_REPORT_PACKAGE_DOCUMENT_TYPE = "https://xbrl.org/report-package/2023"

SUPPORTED_DOCUMENT_TYPES = frozenset(
    [
        INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE,
        NON_INLINE_XBRL_REPORT_PACKAGE_DOCUMENT_TYPE,
        UNCONSTRAINED_REPORT_PACKAGE_DOCUMENT_TYPE,
    ]
)

INLINE_XBRL_REPORT_PACKAGE_EXTENSION = ".xbri"
NON_INLINE_XBRL_REPORT_PACKAGE_EXTENSION = ".xbr"
UNCONSTRAINED_REPORT_PACKAGE_EXTENSION = ".zip"


REPORT_PACKAGE_EXTENSIONS = frozenset(
    [
        INLINE_XBRL_REPORT_PACKAGE_EXTENSION,
        NON_INLINE_XBRL_REPORT_PACKAGE_EXTENSION,
        UNCONSTRAINED_REPORT_PACKAGE_EXTENSION,
        UNCONSTRAINED_REPORT_PACKAGE_EXTENSION.upper(),
    ]
)

REPORT_PACKAGE_FILE = f"{META_INF_DIRECTORY}/reportPackage.json"
REPORTS_DIRECTORY = "reports"
REPORT_PACKAGE_PATHS = [REPORT_PACKAGE_FILE, f"{REPORTS_DIRECTORY}/"]

XBRL_2_1_REPORT_FILE_EXTENSION = ".xbrl"
JSON_REPORT_FILE_EXTENSION = ".json"
NON_INLINE_REPORT_FILE_EXTENSIONS = frozenset([
    XBRL_2_1_REPORT_FILE_EXTENSION,
    JSON_REPORT_FILE_EXTENSION,
])
INLINE_REPORT_FILE_EXTENSIONS = frozenset([".xhtml", ".html", ".htm"])
REPORT_FILE_EXTENSIONS = frozenset(
    [
        *NON_INLINE_REPORT_FILE_EXTENSIONS,
        *INLINE_REPORT_FILE_EXTENSIONS,
    ]
)


class ReportType(Enum):
    INLINE_XBRL_REPORT_PACKAGE = INLINE_XBRL_REPORT_PACKAGE_EXTENSION
    NON_INLINE_XBRL_REPORT_PACKAGE = NON_INLINE_XBRL_REPORT_PACKAGE_EXTENSION
    UNCONSTRAINED_REPORT_PACKAGE = UNCONSTRAINED_REPORT_PACKAGE_EXTENSION

    @staticmethod
    def fromExtension(extension: str) -> ReportType | None:
        for reportType in ReportType:
            if reportType.value == extension.lower():
                return reportType
        return None

    @property
    def reportFileExtensions(self) -> frozenset[str]:
        if self == ReportType.INLINE_XBRL_REPORT_PACKAGE:
            return INLINE_REPORT_FILE_EXTENSIONS
        if self == ReportType.NON_INLINE_XBRL_REPORT_PACKAGE:
            return NON_INLINE_REPORT_FILE_EXTENSIONS
        if self == ReportType.UNCONSTRAINED_REPORT_PACKAGE:
            return REPORT_FILE_EXTENSIONS
        raise ValueError(f"Report type without defined report file extensions: {self}")

    @property
    def isConstrained(self) -> bool:
        return self != ReportType.UNCONSTRAINED_REPORT_PACKAGE
