"""
See COPYRIGHT.md for copyright information.
"""

from __future__ import annotations
import regex as re
from arelle import ModelDocument
from dataclasses import dataclass
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData

TAXONOMY_REFERENCES = [
    "https://xbrl.frc.org.uk/ireland/FRS-101/2019-01-01/ie-FRS-101-2019-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/FRS-101/2022-01-01/ie-FRS-101-2022-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/FRS-101/2023-01-01/ie-FRS-101-2023-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/FRS-102/2019-01-01/ie-FRS-102-2019-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/FRS-102/2022-01-01/ie-FRS-102-2022-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/FRS-102/2023-01-01/ie-FRS-102-2023-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/IFRS/2019-01-01/ie-IFRS-2019-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/IFRS/2022-01-01/ie-IFRS-2022-01-01.xsd",
    "https://xbrl.frc.org.uk/ireland/IFRS/2023-01-01/ie-IFRS-2023-01-01.xsd",
    "https://raw.githubusercontent.com/revenue-ie/dpl/master/schemas/ct/combined/2017-09-01/IE-FRS-101-IE-DPL-2017-09-01.xsd",
    "https://raw.githubusercontent.com/revenue-ie/dpl/master/schemas/ct/combined/2017-09-01/IE-FRS-102-IE-DPL-2017-09-01.xsd",
    "https://raw.githubusercontent.com/revenue-ie/dpl/master/schemas/ct/combined/2017-09-01/IE-EU-IFRS-IE-DPL-2017-09-01.xsd",
]

SCHEMA_PATTERNS = {
    "http://www.revenue.ie/": re.compile(r"^(\d{7}[A-Z]{1,2}|CHY\d{1,5})$"),
    "http://www.cro.ie/": re.compile(r"^\d{1,6}$")
}

TR_NAMESPACES = {
    "http://www.xbrl.org/inlineXBRL/transformation/2010-04-20",
    "http://www.xbrl.org/inlineXBRL/transformation/2011-07-31",
    "http://www.xbrl.org/inlineXBRL/transformation/2015-02-26"
}

MANDATORY_ELEMENTS = {
    "bus": {
        "EntityCurrentLegalOrRegisteredName",
        "StartDateForPeriodCoveredByReport",
        "EndDateForPeriodCoveredByReport"
    },
    "uk-bus": {
        "EntityCurrentLegalOrRegisteredName",
        "StartDateForPeriodCoveredByReport",
        "EndDateForPeriodCoveredByReport",
    },
    "ie-dpl": {
        "DPLTurnoverRevenue",
        "DPLGovernmentGrantIncome",
        "DPLOtherOperatingIncome",
        "DPLGrossProfitLoss",
        "DPLStaffCostsEmployeeBenefitsExpense",
        "DPLSubcontractorCosts",
        "DPLProfitLossBeforeTax"
    },
    "core": {
        "Equity",
    }
}


@dataclass
class PluginValidationDataExtension(PluginData):
    _filingTypes: set[str] | None = None
    _unexpectedTaxonomyReferences: set[str] | None = None
    _numIxDocs: int | None = None

    def filingTypeInformation(self, modelXbrl: ModelXbrl) -> None:
        filingTypes = set()
        unexpectedTaxonomyReferences = set()
        numIxDocs = 0
        for doc in modelXbrl.urlDocs.values():
            if doc.type == ModelDocument.Type.INLINEXBRL:
                numIxDocs += 1
                for referencedDoc in doc.referencesDocument.keys():
                    if referencedDoc.type == ModelDocument.Type.SCHEMA:
                        if referencedDoc.uri in TAXONOMY_REFERENCES:
                            filingTypes.add(referencedDoc.uri)
                        else:
                            unexpectedTaxonomyReferences.add(referencedDoc.uri)

        self._filingTypes = filingTypes
        self._unexpectedTaxonomyReferences = unexpectedTaxonomyReferences
        self._numIxDocs = numIxDocs

    def getFilingTypes(self, modelXbrl: ModelXbrl) -> set[str]:
        if self._filingTypes is None:
            self.filingTypeInformation(modelXbrl)
        return self._filingTypes

    def getNumIxDocs(self, modelXbrl: ModelXbrl) -> int:
        if self._numIxDocs is None:
            self.filingTypeInformation(modelXbrl)
        return self._numIxDocs

    def getUnexpectedTaxonomyReferences(self, modelXbrl: ModelXbrl) -> set[str]:
        if self._unexpectedTaxonomyReferences is None:
            self.filingTypeInformation(modelXbrl)
        return self._unexpectedTaxonomyReferences
