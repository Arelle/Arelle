"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re

from arelle.Cntlr import Cntlr
from arelle.ModelValue import qname
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import (
    NAMESPACE_AUREP,
    NAMESPACE_BUS,
    NAMESPACE_CORE,
    NAMESPACE_DIREP,
    PluginValidationDataExtension,
)

# Regex pattern for FRC taxonomy entry point URLs
FRC_ENTRY_POINT_PATTERN = re.compile(
    r"https?://xbrl\.frc\.org\.uk/"
)


class ValidationPluginExtension(ValidationPlugin):
    """UKSEF validation plugin extension.

    Extends the base ValidationPlugin to provide UKSEF-specific
    plugin data with cached QNames and regex patterns.
    """

    def newPluginData(self, cntlr: Cntlr, validateXbrl: ValidateXbrl | None) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(
            self.name,
            isUksefFiling=False,
            frcEntryPointPattern=FRC_ENTRY_POINT_PATTERN,
            # Dimension QNames
            accountsStatusDimensionQn=qname(f"{{{NAMESPACE_BUS}}}AccountsStatusDimension"),
            scopeAccountsDimensionQn=qname(f"{{{NAMESPACE_BUS}}}ScopeAccountsDimension"),
            # Member QNames
            auditedMemberQn=qname(f"{{{NAMESPACE_BUS}}}Audited"),
            groupAccountsOnlyMemberQn=qname(f"{{{NAMESPACE_BUS}}}GroupAccountsOnly"),
            consolidatedGroupCompanyAccountsMemberQn=qname(f"{{{NAMESPACE_BUS}}}ConsolidatedGroupCompanyAccounts"),
            # Mandatory concept QNames - business namespace
            entityCurrentLegalOrRegisteredNameQn=qname(f"{{{NAMESPACE_BUS}}}EntityCurrentLegalOrRegisteredName"),
            balanceSheetDateQn=qname(f"{{{NAMESPACE_BUS}}}BalanceSheetDate"),
            startDateForPeriodCoveredByReportQn=qname(f"{{{NAMESPACE_BUS}}}StartDateForPeriodCoveredByReport"),
            endDateForPeriodCoveredByReportQn=qname(f"{{{NAMESPACE_BUS}}}EndDateForPeriodCoveredByReport"),
            entityDormantQn=qname(f"{{{NAMESPACE_BUS}}}EntityDormant"),
            entityTradingStatusQn=qname(f"{{{NAMESPACE_BUS}}}EntityTradingStatus"),
            accountsTypeQn=qname(f"{{{NAMESPACE_BUS}}}AccountsType"),
            accountsStatusQn=qname(f"{{{NAMESPACE_BUS}}}AccountsStatus"),
            companyRegistrationNumberQn=qname(f"{{{NAMESPACE_BUS}}}CompanyRegistrationNumber"),
            countryOfIncorporationQn=qname(f"{{{NAMESPACE_BUS}}}CountryOfIncorporation"),
            addressLine1Qn=qname(f"{{{NAMESPACE_BUS}}}AddressLine1"),
            principalLocationQn=qname(f"{{{NAMESPACE_BUS}}}PrincipalLocation"),
            # Mandatory concept QNames - core namespace
            directorSigningFinancialStatementsQn=qname(f"{{{NAMESPACE_CORE}}}DirectorSigningFinancialStatements"),
            dateSigningFinancialStatementsQn=qname(f"{{{NAMESPACE_CORE}}}DateSigningFinancialStatements"),
            # Mandatory concept QNames - aurep namespace
            typeOfAuditorsReportQn=qname(f"{{{NAMESPACE_AUREP}}}TypeOfAuditorsReport"),
            dateAuditorsReportQn=qname(f"{{{NAMESPACE_AUREP}}}DateAuditorsReport"),
            nameIndividualAuditorQn=qname(f"{{{NAMESPACE_AUREP}}}NameIndividualAuditor"),
            nameOfFirmAuditorQn=qname(f"{{{NAMESPACE_AUREP}}}NameOfFirmAuditor"),
            # Mandatory concept QNames - direp namespace
            dateSigningDirectorsReportQn=qname(f"{{{NAMESPACE_DIREP}}}DateSigningDirectorsReport"),
        )
