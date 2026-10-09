"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from arelle.Cntlr import Cntlr
from arelle.ModelValue import QName
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .DisclosureSystems import UKSEF_ONLY_2025
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


def _qnames(prefix: str, namespace: str, *localNames: str) -> tuple[QName, ...]:
    return tuple(QName.fromParts(prefix, namespace, localName) for localName in localNames)


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, cntlr: Cntlr, validateXbrl: ValidateXbrl | None) -> PluginValidationDataExtension:
        pluginData = PluginValidationDataExtension(self.name)
        if validateXbrl is not None and validateXbrl.disclosureSystem.name == UKSEF_ONLY_2025:
            uksef_2025_business = "http://xbrl.frc.org.uk/cd/2025-01-01/business"
            uksef_2025_core = "http://xbrl.frc.org.uk/fr/2025-01-01/core"
            uksef_2025_aurep = "http://xbrl.frc.org.uk/reports/2025-01-01/aurep"
            uksef_2025_direp = "http://xbrl.frc.org.uk/reports/2025-01-01/direp"

            pluginData.uksefMandatoryFacts = (
                *_qnames(
                    "bus",
                    uksef_2025_business,
                    "UKCompaniesHouseRegisteredNumber",
                    "BalanceSheetDate",
                    "StartDateForPeriodCoveredByReport",
                    "EndDateForPeriodCoveredByReport",
                    "EntityCurrentLegalOrRegisteredName",
                ),
                *_qnames(
                    "core",
                    uksef_2025_core,
                    "DateAuthorisationFinancialStatementsForIssue",
                    "DirectorSigningFinancialStatements",
                ),
                *_qnames(
                    "bus",
                    uksef_2025_business,
                    "EntityDormantTruefalse",
                    "EntityTradingStatus",
                    "AccountingStandardsApplied",
                    "AccountsStatusAuditedOrUnaudited",
                    "AccountsType",
                ),
                *_qnames(
                    "core",
                    uksef_2025_core,
                    "AverageNumberEmployeesDuringPeriod",
                    "ProfitLoss",
                ),
            )
            pluginData.uksefGroupAuditedMandatoryFacts = (
                *_qnames("aurep", uksef_2025_aurep, "DateAuditorsReport"),
                *_qnames("bus", uksef_2025_business, "NameEntityAuditors"),
                *_qnames("aurep", uksef_2025_aurep, "NameSeniorStatutoryAuditor"),
                *_qnames("direp", uksef_2025_direp, "DateSigningDirectorsReport", "DirectorSigningDirectorsReport"),
            )
            pluginData.uksefAuditorOpinionAlternatives = _qnames(
                "aurep",
                uksef_2025_aurep,
                "OpinionAuditorsOnEntity",
                "NamedIndividualAuditor",
            )
        return pluginData
