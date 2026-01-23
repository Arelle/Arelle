"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import regex
from functools import lru_cache

from arelle.ModelInstanceObject import ModelContext, ModelFact
from arelle.ModelValue import QName
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData
from arelle.XmlValidateConst import VALID


@dataclass
class PluginValidationDataExtension(PluginData):
    accountingPolicyConceptQns: frozenset[QName]
    addressOfSubmittingEnterprisePostcodeAndTownQn: QName
    addressOfSubmittingEnterpriseStreetAndNumberQn: QName
    allReportingPeriodsMemberQn: QName
    annualReportTypes: frozenset[str]
    assetsQn: QName
    auditedAssuranceReportsDanish: str
    auditedAssuranceReportsEnglish: str
    auditedExtendedReviewDanish: str
    auditedExtendedReviewEnglish: str
    auditedFinancialStatementsDanish: str
    auditedFinancialStatementsEnglish: str
    auditedNonAssuranceReportsDanish: str
    auditedNonAssuranceReportsEnglish: str
    averageNumberOfEmployeesQn: QName
    balanceSheetQnLessThanOrEqualToAssets: frozenset[QName]
    basisForAdverseOpinionDanish: str
    basisForAdverseOpinionEnglish: str
    basisForDisclaimerOpinionDanish: str
    basisForDisclaimerOpinionEnglish: str
    basisForQualifiedOpinionDanish: str
    basisForQualifiedOpinionEnglish: str
    cClassOfReportingEntityEnums: frozenset[str]
    classOfReportingEntityQn: QName
    dClassOfReportingEntityEnums: frozenset[str]
    disclosureOfEquityQns: frozenset[QName]
    consolidatedMemberQn: QName
    consolidatedSoloDimensionQn: QName
    cpr_regex: regex.Pattern[str]
    dateOfApprovalOfAnnualReportQn: QName
    dateOfExtraordinaryDividendDistributedAfterEndOfReportingPeriod: QName
    dateOfGeneralMeetingQn: QName
    descriptionOfQualificationsOfAssuranceEngagementPerformedQn: QName
    descriptionOfQualificationsOfAuditedFinancialStatementsQn: QName
    descriptionOfQualificationsOfFinancialStatementsExtendedReviewQn: QName
    descriptionsOfQualificationsOfReviewedFinancialStatementsQn: QName
    declarationObligationQns: frozenset[QName]
    distributionOfResultsQns: frozenset[QName]
    employeeBenefitsExpenseQn: QName
    equityQn: QName
    endDateForUseOfDigitalNonregisteredBookkeepingSystemQn: QName
    endDateForUseOfDigitalStandardBookkeepingSystemQn: QName
    extraordinaryCostsQn: QName
    extraordinaryIncomeQn: QName
    extraordinaryResultBeforeTaxQn: QName
    fr37RestrictedText: str
    forbiddenTypeOfSubmittedReportEnumerations: frozenset[str]
    hasNotGivenRiseToReservationsText: frozenset[str]
    identificationNumberCvrOfAuditFirmQn: QName
    identificationNumberCvrOfReportingEntityQn: QName
    independentAuditorsReportDanish: str
    independentAuditorsReportEnglish: str
    independentAuditorsReportReviewDanish: str
    independentAuditorsReportReviewEnglish: str
    independentPractitionersExtendedReviewReportDanish: str
    independentPractitionersExtendedReviewReportEnglish: str
    independentPractitionersReviewReportDanish: str
    independentPractitionersReviewReportEnglish: str
    informationOnTypeOfSubmittedReportQn: QName
    legalEntityIdentifierOfReportingEntityQn: QName
    liabilitiesQn: QName
    liabilitiesAndEquityQn: QName
    liabilitiesOtherThanProvisionsQn: QName
    longtermLiabilitiesOtherThanProvisionsQn: QName
    managementEndorsementQns: frozenset[QName]
    noncurrentAssetsQn: QName
    nameAndSurnameOfChairmanOfGeneralMeetingQn: QName
    nameOfAuditFirmQn: QName
    nameOfReportingEntityQn: QName
    nameOfSubmittingEnterpriseQn: QName
    otherEmployeeExpenseQn: QName
    positiveProfitThreshold: float
    postemploymentBenefitExpenseQn: QName
    precedingReportingPeriodEndDateQn: QName
    precedingReportingPeriodStartDateQn: QName
    profitLossQn: QName
    proposedDividendRecognisedInEquityQn: QName
    proposedExtraordinaryDividendRecognisedInLiabilitiesQn: QName
    provisionsQn: QName
    registrationNumberOfTheDigitalStandardBookkeepingSystemUsedQn: QName
    registeredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMemberQn: QName
    reportingClassCLargeDanish: str
    reportingClassCLargeEnglish: str
    reportingClassCLargeLowercaseDanish: str
    reportingClassCLargeLowercaseEnglish: str
    reportingClassCMediumDanish: str
    reportingClassCMediumEnglish: str
    reportingClassCMediumLowercaseDanish: str
    reportingClassCMediumLowercaseEnglish: str
    reportingClassDDanish: str
    reportingClassDEnglish: str
    reportingClassDLowercaseDanish: str
    reportingClassDLowercaseEnglish: str
    reportingPeriodEndDateQn: QName
    reportingPeriodStartDateQn: QName
    reportingResponsibilitiesOnApprovedAuditorsReportAuditQn: QName
    reportingResponsibilitiesOnApprovedAuditorsReportsExtendedReviewQn: QName
    reportingObligationQns: frozenset[QName]
    schemaRefUri: str
    selectedElementsFromReportingClassCQn: QName
    selectedElementsFromReportingClassDQn: QName
    shorttermLiabilitiesOtherThanProvisionsQn: QName
    signatureOfAuditorsDateQn: QName
    soloMemberQn: QName
    startDateForUseOfDigitalNonregisteredBookkeepingSystemQn: QName
    startDateForUseOfDigitalStandardBookkeepingSystemQn: QName
    statementOfChangesInEquityQns: frozenset[QName]
    taxExpenseOnOrdinaryActivitiesQn: QName
    taxExpenseQn: QName
    typeOfAuditorAssistanceQn: QName
    typeOfBasisForModifiedOpinionOnFinancialStatementsReviewQn: QName
    typeOfDigitalNonregisteredBookkeepingSystemQn: QName
    typeOfReportingPeriodDimensionQn: QName
    wagesAndSalariesQn: QName

    # Identity hash for caching.
    def __hash__(self) -> int:
        return id(self)

    @lru_cache(1)
    def contextFactMap(self, modelXbrl: ModelXbrl) -> dict[str, dict[QName, ModelFact]]:
        contextFactMap: dict[str, dict[QName, ModelFact]] = defaultdict(dict)
        for fact in modelXbrl.facts:
            contextFactMap[fact.contextID][fact.qname] = fact
        return contextFactMap

    def getCurrentAndPreviousReportingPeriodContexts(self, modelXbrl: ModelXbrl) -> list[ModelContext]:
        """
        :return: Returns the most recent reporting period contexts (at most two).
        """
        contexts = self.getReportingPeriodContexts(modelXbrl)
        if not contexts:
            return contexts
        if len(contexts) > 2:
            return contexts[-2:]
        return contexts

    @lru_cache(1)
    def getReportingPeriodContexts(self, modelXbrl: ModelXbrl) -> list[ModelContext]:
        """
        :return: A sorted list of contexts that match "reporting period" criteria.
        """
        contexts = []
        for context in modelXbrl.contexts.values():
            if context.isInstantPeriod or context.isForeverPeriod:
                continue  # Reporting period contexts can't be instant/forever contexts
            if context.startDatetime is None or context.endDatetime is None:
                continue  # Incomplete context
            if len(context.qnameDims) > 0:
                if context.qnameDims.keys() != {self.consolidatedSoloDimensionQn}:
                    continue  # Context is dimensionalized with something other than consolidatedSoloDimensionQn
                if context.dimMemberQname(self.consolidatedSoloDimensionQn) != self.consolidatedMemberQn:
                    continue  # Context is dimensionalized with the correct dimension but not member
            contexts.append(context)
        return sorted(contexts, key=lambda c: c.endDatetime)

    def isAnnualReport(self, modelXbrl: ModelXbrl) -> bool:
        """
        :return: Return True if Type of Submitted Report value is in the annual report types
        """
        reportTypeFacts = modelXbrl.factsByQname.get(self.informationOnTypeOfSubmittedReportQn, set())
        filteredReportTypeFacts = [f for f in reportTypeFacts if f.xValid >= VALID and f.xValue in self.annualReportTypes]
        return len(filteredReportTypeFacts) > 0
