"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arelle import PluginManager, PackageManager
from arelle.packages.report.ReportPackageValidator import ReportPackageValidator

if TYPE_CHECKING:
    from arelle.Cntlr import Cntlr
    from arelle.FileSource import FileSource


class ValidateFileSource:
    def __init__(self, cntrl: Cntlr, filesource: FileSource):
        self._cntrl = cntrl
        self._filesource = filesource

    def validate(self, forceValidateAsReportPackages: bool = False, forceValidateAsTaxonomyPackage: bool = False, errors: list[str] | None = None) -> None:
        for pluginXbrlMethod in PluginManager.pluginClassMethods("Validate.FileSource"):
            pluginXbrlMethod(self._cntrl, self._filesource)
        if self._filesource.isReportPackage or forceValidateAsReportPackages:
            rpValidator = ReportPackageValidator(self._filesource)
            for val in rpValidator.validate():
                codes = [val.codes] if isinstance(val.codes, str) else val.codes
                for code in codes:
                    self._cntrl.error(
                        level=val.level.name,
                        codes=code,
                        msg=val.msg,
                        fileSource=self._filesource,
                        **val.args
                    )
                    if errors is not None:
                        errors.append(code)
        # Automatically validates a report package as a taxonomy package if a
        # taxonomy package metadata file exists.
        self._filesource.loadTaxonomyPackageMappings(
            errors=errors,
            expectTaxonomyPackage=forceValidateAsTaxonomyPackage
        )
