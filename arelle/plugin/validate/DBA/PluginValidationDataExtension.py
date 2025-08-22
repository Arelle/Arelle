"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import cast

import regex

from arelle.ModelInstanceObject import ModelFact, ModelContext
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
    cpr_regex: regex.regex.Pattern[str]
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
    registeredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMemberQn: QName
    reportingClassCLargeDanish: str
    reportingClassCLargeEnglish: str
    reportingClassCMediumDanish: str
    reportingClassCMediumEnglish: str
    reportingClassDDanish: str
    reportingClassDEnglish: str
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
    statementOfChangesInEquityQns: frozenset[QName]
    taxExpenseOnOrdinaryActivitiesQn: QName
    taxExpenseQn: QName
    typeOfAuditorAssistanceDanish: str
    typeOfAuditorAssistanceEnglish: str
    typeOfAuditorAssistanceQn: QName
    typeOfBasisForModifiedOpinionOnFinancialStatementsReviewQn: QName
    typeOfReportingPeriodDimensionQn: QName
    wagesAndSalariesQn: QName

    _contextFactMap: dict[str, dict[QName, ModelFact]] | None = None
    _reportingPeriodContexts: list[ModelContext] | None = None

    def contextFactMap(self, modelXbrl: ModelXbrl) -> dict[str, dict[QName, ModelFact]]:
        if self._contextFactMap is None:
            self._contextFactMap = defaultdict(dict)
            for fact in modelXbrl.facts:
                self._contextFactMap[fact.contextID][fact.qname] = fact
        return self._contextFactMap

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

    def getReportingPeriodContexts(self, modelXbrl: ModelXbrl) -> list[ModelContext]:
        """
        :return: A sorted list of contexts that match "reporting period" criteria.
        """
        if self._reportingPeriodContexts is not None:
            return self._reportingPeriodContexts
        contexts = []
        for context in modelXbrl.contexts.values():
            if context.isInstantPeriod or context.isForeverPeriod:
                continue  # Reporting period contexts can't be instant/forever contexts
            if len(context.qnameDims) > 0:
                if context.qnameDims.keys() != {self.consolidatedSoloDimensionQn}:
                    continue  # Context is dimensionalized with something other than consolidatedSoloDimensionQn
                if context.dimMemberQname(self.consolidatedSoloDimensionQn) != self.consolidatedMemberQn:
                    continue  # Context is dimensionalized with the correct dimension but not member
            contexts.append(context)
        self._reportingPeriodContexts = sorted(contexts, key=lambda c: c.endDatetime)
        return self._reportingPeriodContexts

    def isAnnualReport(self, modelXbrl: ModelXbrl) -> bool:
        """
        :return: Return True if Type of Submitted Report value is in the annual report types
        """
        reportTypeFacts = modelXbrl.factsByQname.get(self.informationOnTypeOfSubmittedReportQn, set())
        filteredReportTypeFacts = [f for f in reportTypeFacts if f.xValid >= VALID and f.xValue in self.annualReportTypes]
        return len(filteredReportTypeFacts) > 0
