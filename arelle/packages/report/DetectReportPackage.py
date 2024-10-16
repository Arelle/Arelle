"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from pathlib import Path

from arelle.packages.report import ReportPackageConst


def isReportPackageExtension(filename: str) -> bool:
    return Path(filename).suffix in ReportPackageConst.REPORT_PACKAGE_EXTENSIONS
