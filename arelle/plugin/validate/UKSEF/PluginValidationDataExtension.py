"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from arelle.ModelValue import QName
from arelle.utils.PluginData import PluginData


NAMESPACE_BUS = "http://xbrl.frc.org.uk/cd/2025-01-01/business"
NAMESPACE_CORE = "http://xbrl.frc.org.uk/fr/2025-01-01/core"
NAMESPACE_AUREP = "http://xbrl.frc.org.uk/reports/2025-01-01/aurep"
NAMESPACE_DIREP = "http://xbrl.frc.org.uk/reports/2025-01-01/direp"


@dataclass
class PluginValidationDataExtension(PluginData):
    """Plugin data extension for UKSEF validation.

    Caches pre-compiled regexes, QNames for mandatory concepts,
    and dimension/member QNames used across rule functions.
    """

    isUksefFiling: bool
    frcEntryPointPattern: re.Pattern[str]

    # Dimension QNames
    accountsStatusDimensionQn: QName
    scopeAccountsDimensionQn: QName

    # Member QNames
    auditedMemberQn: QName
    groupAccountsOnlyMemberQn: QName
    consolidatedGroupCompanyAccountsMemberQn: QName

    # Mandatory concept QNames - business namespace
    entityCurrentLegalOrRegisteredNameQn: QName
    balanceSheetDateQn: QName
    startDateForPeriodCoveredByReportQn: QName
    endDateForPeriodCoveredByReportQn: QName
    entityDormantQn: QName
    entityTradingStatusQn: QName
    accountsTypeQn: QName
    accountsStatusQn: QName
    companyRegistrationNumberQn: QName
    countryOfIncorporationQn: QName
    addressLine1Qn: QName
    principalLocationQn: QName

    # Mandatory concept QNames - core namespace
    directorSigningFinancialStatementsQn: QName
    dateSigningFinancialStatementsQn: QName

    # Mandatory concept QNames - aurep namespace
    typeOfAuditorsReportQn: QName
    dateAuditorsReportQn: QName
    nameIndividualAuditorQn: QName
    nameOfFirmAuditorQn: QName

    # Mandatory concept QNames - direp namespace
    dateSigningDirectorsReportQn: QName

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)
