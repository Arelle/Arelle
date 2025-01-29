"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import decimal
from collections.abc import Iterable
from typing import Any, cast

from arelle.XbrlConst import xhtml
from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from . import errorOnDateFactComparison, errorOnRequiredFact, getFactsWithDimension, getFactsGroupedByContextId, errorOnRequiredPositiveFact, getFactsWithoutDimension, groupFactsByContextHash, \
    minimumRequiredFactsFound
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..ValidationPluginExtension import DANISH_CURRENCY_ID, ROUNDING_MARGIN, PERSONNEL_EXPENSE_THRESHOLD, REQUIRED_DISCLOSURE_OF_EQUITY_FACTS, REQUIRED_STATEMENT_OF_CHANGES_IN_EQUITY_FACTS

_: TypeGetText

@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR1: First and last name of the conductor for the general meeting or person who takes the conductor's place is missing
    Companies that hold a general meeting and therefore provide a general meeting date
    (gsd:DateOfGeneralMeeting) must also provide the name of the director
    (gsd:NameAndSurnameOfChairmanOfGeneralMeeting).
    """
    meetingFacts = val.modelXbrl.factsByQname.get(pluginData.dateOfGeneralMeetingQn, set())
    if len(meetingFacts) > 0:
        chairmanFacts = val.modelXbrl.factsByQname.get(pluginData.nameAndSurnameOfChairmanOfGeneralMeetingQn, set())
        if len(chairmanFacts) == 0:
            yield Validation.error(
                codes="DBA.FR1",
                msg=_("First and last name of the conductor for the general meeting or person who takes the conductor's place is missing"),
                modelObject=[val.modelXbrl.modelDocument]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR7: Date of approval of the annual report (gsd:DateOfApprovalOfAnnualReport)
    must be after the end date of the Accounting Period (gsd:ReportingPeriodEndDate
    with default TypeOfReportingPeriodDimension).
    """
    return errorOnDateFactComparison(
        val.modelXbrl,
        fact1Qn=pluginData.reportingPeriodEndDateQn,
        fact2Qn=pluginData.dateOfApprovalOfAnnualReportQn,
        dimensionQn=pluginData.typeOfReportingPeriodDimensionQn,
        code='DBA.FR7',
        message=_("Date of approval of the annual report='%(fact2)s' "
                  "must be after the end date of the accounting period='%(fact1)s'"),
        assertion=lambda endDate, approvalDate: endDate < approvalDate,
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR20: The annual report is missing a management endorsement. An annual report must always contain a management
    endorsement if the company has more than one management member or if the company prepares an annual report according
    to accounting class D.
    """
    modelXbrl = val.modelXbrl
    for concept_qn in pluginData.managementEndorsementQns:
        facts = modelXbrl.factsByQname.get(concept_qn, set())
        for fact in facts:
            if fact.xValid >= VALID and not fact.isNil:
                return
    yield Validation.error(
        codes="DBA.FR20",
        msg=_("The annual report does not contain a management endorsement. Please tag one of the following elements: {}").format(
            [qn.localName for qn in pluginData.managementEndorsementQns]
        ),
        modelObject=val.modelXbrl.modelDocument
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr24(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR24: When cmn:TypeOfAuditorAssistance is "Revisionspåtegning" or "Auditor's report on audited financial statements"
    then arr:DescriptionOfQualificationsOfAuditedFinancialStatements must not contain the following text:
        - 'har ikke givet anledning til forbehold'
        - 'has not given rise to reservations'
    """
    modelXbrl = val.modelXbrl
    type_of_auditors_assistance_facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for auditor_fact in type_of_auditors_assistance_facts:
        if (auditor_fact.xValid >= VALID and
                (auditor_fact.xValue == pluginData.auditedFinancialStatementsDanish or
                 auditor_fact.xValue == pluginData.auditedFinancialStatementsEnglish)):
            description_facts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfAuditedFinancialStatementsQn, set())
            for description_fact in description_facts:
                if description_fact.xValid >= VALID:
                    for text in pluginData.hasNotGivenRiseToReservationsText:
                        if text in str(description_fact.xValue):
                            yield Validation.error(
                                codes="DBA.FR24",
                                msg=_("The value of DescriptionOfQualificationsOfAuditedFinancialStatements must not "
                                      "contain the text: \'{}\', when TypeOfAuditorAssistance is set to \'Revisionspåtegning\' "
                                      "or \'Auditor's report on audited financial statements\'").format(text),
                                modelObject=description_fact
                            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr25(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR25: When cmn:TypeOfAuditorAssistance is "Erklæring om udvidet gennemgang" or "Auditor's report on extended review"
    then arr:DescriptionOfQualificationsOfFinancialStatementsExtendedReview must not contain the following text:
        - 'har ikke givet anledning til forbehold'
        - 'has not given rise to reservations'
    """
    modelXbrl = val.modelXbrl
    type_of_auditors_assistance_facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for auditor_fact in type_of_auditors_assistance_facts:
        if (auditor_fact.xValid >= VALID and
                (auditor_fact.xValue == pluginData.auditedExtendedReviewDanish or
                 auditor_fact.xValue == pluginData.auditedExtendedReviewEnglish)):
            description_facts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfFinancialStatementsExtendedReviewQn, set())
            for description_fact in description_facts:
                if description_fact.xValid >= VALID:
                    for text in pluginData.hasNotGivenRiseToReservationsText:
                        if text in str(description_fact.xValue):
                            yield Validation.error(
                                codes="DBA.FR25",
                                msg=_("The value of DescriptionOfQualificationsOfFinancialStatementsExtendedReview must not "
                                      "contain the text: \'{}\', when TypeOfAuditorAssistance is set to \'Erklæring om udvidet "
                                      "gennemgang\' or \'Auditor's report on extended review\'").format(text),
                                modelObject=description_fact
                            )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr33(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR33: For groups in accounting classes C and D, either Statement of changes in equity [hierarchy:fsa:StatementOfChangesInEquity] must have a minimum of three fields filled in from
    [hierarchy:fsa:StatementOfChangesInEquity] or two fields in
    Information on equity [hierarchy:fsa:DisclosureOfEquity].
    """
    reportingClass = False
    classOfReportingEntityFacts = val.modelXbrl.factsByQname.get(pluginData.classOfReportingEntityQn, set())
    for fact in classOfReportingEntityFacts:
        if fact is not None and fact.xValid >= VALID:
            if fact.xValue in pluginData.cClassOfReportingEntityEnums or fact.xValue in pluginData.dClassOfReportingEntityEnums:
                reportingClass = True
                break
    if not reportingClass:
        reportingClass = any(
            fact and fact.xValid >= VALID
            for fact in val.modelXbrl.factsByQname.get(pluginData.selectedElementsFromReportingClassCQn, set())
        )
    if not reportingClass:
        reportingClass = any(
            fact and fact.xValid >= VALID
            for fact in val.modelXbrl.factsByQname.get(pluginData.selectedElementsFromReportingClassDQn, set())
        )
    if reportingClass:
        if not minimumRequiredFactsFound(val.modelXbrl, pluginData.disclosureOfEquityQns, REQUIRED_DISCLOSURE_OF_EQUITY_FACTS):
            if not minimumRequiredFactsFound(val.modelXbrl, pluginData.statementOfChangesInEquityQns, REQUIRED_STATEMENT_OF_CHANGES_IN_EQUITY_FACTS):
                yield Validation.error(
                    codes="DBA.FR33",
                    msg=_("For groups in accounting classes C and D, either Statement of Changes in Equity '[hierarchy:fsa:StatementOfChangesInEquity]' must have a minimum of three fields filled in "
                          "Or two fields in Information on Equity [hierarchy:fsa:DisclosureOfEquity] ."),
                    modelObject=val.modelXbrl.modelDocument
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr34(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR34: If Equity does not equal 0 more fields are required.  At least one field must be filled in on the balance sheet in addition to equity:
    Assets, NoncurrentAssets, CurrentAssets, LongtermLiabilitiesOtherThanProvisions, ShorttermLiabilitiesOtherThanProvisions, LiabilitiesOtherThanProvisions, LiabilitiesAndEquity
    """
    equityFacts = val.modelXbrl.factsByQname.get(pluginData.equityQn, set())
    nonZeroEquityFacts = []
    for fact in equityFacts:
        if fact.xValid >= VALID:
            if fact.xValue != 0:
                nonZeroEquityFacts.append(fact)
    if nonZeroEquityFacts:
        otherRequiredFactsQnames = [
            pluginData.assetsQn, pluginData.noncurrentAssetsQn, pluginData.longtermLiabilitiesOtherThanProvisionsQn,
            pluginData.shorttermLiabilitiesOtherThanProvisionsQn, pluginData.liabilitiesOtherThanProvisionsQn, pluginData.liabilitiesAndEquityQn
        ]
        hasEquityRequiredFacts = any(val.modelXbrl.factsByQname.get(factQname, set()) for factQname in otherRequiredFactsQnames)
        if not hasEquityRequiredFacts:
            yield Validation.error(
                codes="DBA.FR34",
                msg=_("If Equity is filled in and is not zero, at least one other field must also be filled in: "
                        "Assets, NoncurrentAssets, CurrentAssets, LongtermLiabilitiesOtherThanProvisions, ShorttermLiabilitiesOtherThanProvisions, "
                        "LiabilitiesOtherThanProvisions, LiabilitiesAndEquity."),
                modelObject=nonZeroEquityFacts
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
 )
def rule_fr35(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR35: The annual report does not contain a section on applied accounting practices. The annual report must
    contain a section on the accounting practices used.
    """
    modelXbrl = val.modelXbrl
    for concept_qn in pluginData.accountingPolicyConceptQns:
        facts = modelXbrl.factsByQname.get(concept_qn, set())
        for fact in facts:
            if fact.xValid >= VALID and not fact.isNil:
                return
    yield Validation.error(
        codes="DBA.FR35",
        msg=_("The annual report does not contain information on applied accounting practices. Please tag one of the following elements: {}").format(
            [qn.localName for qn in pluginData.accountingPolicyConceptQns]
        ),
        modelObject=val.modelXbrl.modelDocument
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr36(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR36: arr:DescriptionsOfQualificationsOfReviewedFinancialStatements must not contain the following text:
        - 'har ikke givet anledning til forbehold'
        - 'has not given rise to reservations'
    """
    modelXbrl = val.modelXbrl
    description_facts = modelXbrl.factsByQname.get(pluginData.descriptionsOfQualificationsOfReviewedFinancialStatementsQn, set())
    for description_fact in description_facts:
        if description_fact.xValid >= VALID:
            for text in pluginData.hasNotGivenRiseToReservationsText:
                if text in str(description_fact.xValue):
                    yield Validation.error(
                        codes="DBA.FR36",
                        msg=_("The value of DescriptionsOfQualificationsOfReviewedFinancialStatements must not contain the text: \'{}\'".format(text)),
                        modelObject=description_fact
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr37(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR37: arr:DescriptionOfQualificationsOfAssuranceEngagementPerformed must not contain the following text:
        - 'har ikke givet anledning til forbehold'
        - 'has not given rise to reservations'
    """
    modelXbrl = val.modelXbrl
    description_facts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfAssuranceEngagementPerformedQn, set())
    for description_fact in description_facts:
        if description_fact.xValid >= VALID:
            for text in pluginData.hasNotGivenRiseToReservationsText:
                if text in str(description_fact.xValue):
                    yield Validation.error(
                        codes="DBA.FR37",
                        msg=_("The value of DescriptionOfQualificationsOfAssuranceEngagementPerformed must not contain the text: \'{}\'".format(text)),
                        modelObject=description_fact
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr41(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR41: Failure to fill in 'Tax on profit for the year' or 'Tax on ordinary profit'

    If the result for the year is positive(fsa:ProfitLoss) (defined as greater than DKK 1000),
    either Tax on the year's result (fsa:TaxExpense) or Tax on ordinary result
    (fsa:TaxExpenseOnOrdinaryActivities) must be filled in.

    The control does not look at I/S (partnership), K/S (limited partnership) and P/S
    (partner company, like an LLC). (based on what legal form the identification number is
    registered as in the business register).

    Implementation: For each reporting period context that has a fsa:ProfitLoss fact above
    the threshold, check if there is either a non-nil fsa:TaxExpense or fsa:TaxExpenseOnOrdinaryActivities
    fact in the same context. If not, trigger an error.
    """

    # TODO: There appears to be criteria that exempt some filings from this rule.
    # The criteria is based on the legal form of the company, which may or may not be
    # something we can determine from the identification number and/or other instance data.
    # Once we determine if/how that criteria can be implemented, we can add it here.

    modelXbrl = val.modelXbrl
    contextIds = {c.id for c in pluginData.getCurrentAndPreviousReportingPeriodContexts(modelXbrl)}
    contextMap = {k: v for k, v in pluginData.contextFactMap(modelXbrl).items() if k in contextIds}
    for contextId, factMap in contextMap.items():
        profitLossFact = factMap.get(pluginData.profitLossQn)
        if profitLossFact is None:
            continue

        if profitLossFact.xValid >= VALID and cast(decimal.Decimal, profitLossFact.xValue) <= pluginData.positiveProfitThreshold:
            continue
        taxExpenseFact = factMap.get(pluginData.taxExpenseQn)
        if taxExpenseFact is not None and not taxExpenseFact.isNil:
            continue
        taxExpenseOnOrdinaryActivitiesFact = factMap.get(pluginData.taxExpenseOnOrdinaryActivitiesQn)
        if taxExpenseOnOrdinaryActivitiesFact is not None and not taxExpenseOnOrdinaryActivitiesFact.isNil:
            continue
        yield Validation.warning(
            codes='DBA.FR41',
            msg=_("The annual report does not contain information on tax "
                  "on the year's profit. If the profit for the year in the income "
                  "statement is positive, either 'Tax on profit for the year' or "
                  "'Tax on ordinary profit' must be filled in."),
            modelObject=profitLossFact,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr48(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR48: Annual reports with a start date of 1/1 2016 or later may not use the fields:
    'Extraordinary result before tax',
    'Extraordinary income',
    'Extraordinary costs',
    as §30 of the Annual Accounts Act is repealed."
    """
    disallowedFactQnames = [pluginData.extraordinaryCostsQn, pluginData.extraordinaryIncomeQn, pluginData.extraordinaryResultBeforeTaxQn]
    foundFacts = []
    for factQname in disallowedFactQnames:
        facts = val.modelXbrl.factsByQname.get(factQname, set())
        if len(facts) > 0:
            foundFacts.append(facts)
    if len(foundFacts) > 0:
        yield Validation.warning(
            codes="DBA.FR48",
            msg=_("Annual reports with a start date of 1/1 2016 or later must not use the fields:"
                  "'Extraordinary profit before tax', 'Extraordinary income', 'Extraordinary costs'."),
            modelObject=foundFacts
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr52(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR52: Any usage of fsa:ProposedExtraordinaryDividendRecognisedInLiabilities is prohibited.
    """
    modelXbrl = val.modelXbrl
    facts = modelXbrl.factsByQname.get(pluginData.proposedExtraordinaryDividendRecognisedInLiabilitiesQn, set())
    if len(facts) > 0:
        yield Validation.warning(
            codes='DBA.FR52',
            msg=_("The concept ProposedExtraordinaryDividendRecognisedInLiabilities should not be used"),
            modelObject=facts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr53(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR53: Information is missing on the audit company's CVR no. and the audit firm's name.

    The audit firm's CVR number and name of audit firm should be provided when (fsa:TypeOfAuditorAssistance) is
    tagged with one of the following values:
    - (Revisionspåtegning)  / (Auditor's report on audited financial statements)
    - (Erklæring om udvidet gennemgang) / (Auditor's report on extended review)
    - (Den uafhængige revisors erklæringer (review)) / (The independent auditor's reports (Review))
    - (Andre erklæringer med sikkerhed) / (The independent auditor's reports (Other assurance Reports))
    """
    modelXbrl = val.modelXbrl
    facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for fact in facts:
        if fact.xValid >= VALID:
            if fact.xValue in [
                pluginData.auditedFinancialStatementsDanish,
                pluginData.auditedFinancialStatementsEnglish,
                pluginData.auditedExtendedReviewDanish,
                pluginData.auditedExtendedReviewEnglish,
                pluginData.independentAuditorsReportDanish,
                pluginData.independentAuditorsReportEnglish,
                pluginData.auditedAssuranceReportsDanish,
                pluginData.auditedAssuranceReportsEnglish
            ]:
                missing_concepts = []
                cvr_facts = modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfAuditFirmQn, set())
                auditor_name_facts = modelXbrl.factsByQname.get(pluginData.nameOfAuditFirmQn, set())
                if len(cvr_facts) == 0:
                    missing_concepts.append(pluginData.identificationNumberCvrOfAuditFirmQn.localName)
                if len(auditor_name_facts) == 0:
                    missing_concepts.append(pluginData.nameOfAuditFirmQn.localName)
                if len(missing_concepts) > 0:
                    yield Validation.warning(
                        codes='DBA.FR53',
                        msg=_("The following concepts should be tagged: {} when {} is tagged with the value of {}").format(
                            ",".join(missing_concepts),
                            pluginData.typeOfAuditorAssistanceQn.localName,
                            fact.xValue
                        ),
                        modelObject=fact
                    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr56(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR56: Missing allocation of profit. The annual report must contain a
    distribution of results.

    Annual reports, etc. with a start date of 1/1 2016 or later must have a profit
    allocation, if the profit (fsa:ProfitLoss) for the year is greater than 1000 or
    less than -1000, cf. the Annual Accounts Act §§ 31 and 95 a.
    """
    modelXbrl = val.modelXbrl
    contextIds = {c.id for c in pluginData.getCurrentAndPreviousReportingPeriodContexts(modelXbrl)}
    profitLossFactsMap = getFactsGroupedByContextId(modelXbrl, pluginData.profitLossQn)
    distributionFactsMap = getFactsGroupedByContextId(
        modelXbrl,
        *pluginData.distributionOfResultsQns,
    )
    for contextId, profitLossFacts in profitLossFactsMap.items():
        if contextId not in contextIds:
            continue
        profitLossFact = None
        for fact in profitLossFacts:
            if fact.xValid >= VALID:
                profitLossValue = cast(decimal.Decimal, fact.xValue)
                if not (-pluginData.positiveProfitThreshold <= profitLossValue <= pluginData.positiveProfitThreshold):
                    profitLossFact = fact
                    break
        if profitLossFact is None:
            continue
        distributionFacts = distributionFactsMap.get(contextId, [])
        valid = False
        for distributionsResultDistributionFact in distributionFacts:
            if not distributionsResultDistributionFact.isNil:
                valid = True
                break
        if not valid:
            yield Validation.warning(
                codes='DBA.FR56',
                msg=_("The annual report does not contain a profit distribution. "
                      "The annual report must contain a profit and loss statement with a "
                      "distribution of profits."),
                modelObject=profitLossFact
            )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr59(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR59: When the annual report contains an audit report, which is when TypeOfAuditorAssistance = Revisionspåtegning / Auditor's report on audited financial statements, then the concept
    arr:DescriptionOfQualificationsOfAuditedFinancialStatement must be filled in.
    """
    modelXbrl = val.modelXbrl
    descriptonFacts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfAuditedFinancialStatementsQn)
    indicatorFacts = []
    if descriptonFacts is not None:
        return
    auditorFacts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn)
    if auditorFacts is not None:
        for aFact in auditorFacts:
            if aFact.xValid >= VALID:
                if aFact.xValue in [
                    pluginData.auditedFinancialStatementsDanish,
                    pluginData.auditedFinancialStatementsEnglish,
                ]:
                    indicatorFacts.append(aFact)
        if len(indicatorFacts) > 0:
            yield Validation.error(
                codes='DBA.FR59',
                msg=_("DescriptionOfQualificationsOfAuditedFinancialStatement must be tagged when {} is tagged with the value of {}").format(
                    pluginData.typeOfAuditorAssistanceQn.localName,
                    indicatorFacts[0].xValue),
                    modelObject=indicatorFacts[0])


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr58(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR58: If fsa:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportAudit is tagged then one of the following concepts MUST also be tagged:
    fsa:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCriminalCodeAndFiscalTaxAndSubsidyLegislationAudit
    fsa:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCompaniesActOrEquivalentLegislationThatTheCompanyIsSubjectToAudit
    fsa:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyLegislationOnFinancialReportingIncludingAccountingAndStorageOfAccountingRecordsAudit
    fsa:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyOtherMattersAudit

    """
    modelXbrl = val.modelXbrl
    indicatorFacts = modelXbrl.factsByQname.get(pluginData.reportingResponsibilitiesOnApprovedAuditorsReportAuditQn, set())
    if len(indicatorFacts) > 0:
        for qname in pluginData.declarationObligationQns:
            facts = modelXbrl.factsByQname.get(qname, set())
            if len(facts) > 0:
                return
        yield Validation.warning(
            codes='DBA.FR58',
            msg=_("When the field 'Declaration obligations according to the declaration order ' (ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportAudit) is completed, "
                    "one or more of the sub-items below must be indicated: "
                    "Declaration obligations according to the declaration order, including especially the Criminal Code as well as tax, levy and subsidy legislation (audit) (ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCriminalCodeAndFiscalTaxAndSubsidyLegislationAudit)"
                    "Declaration obligations according to the declaration order, including especially the company law or similar legislation laid down for the company (audit) (ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCompaniesActOrEquivalentLegislationThatTheCompanyIsSubjectToAudit)"
                    "Declaration obligations according to the declaration order, including especially the legislation on financial reporting, including on bookkeeping and storage of accounting material (audit) (ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyLegislationOnFinancialReportingIncludingAccountingAndStorageOfAccountingRecordsAudit)"
                    "Declaration obligations according to the declaration order, including other matters in particular (revision (ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyOtherMattersAudit)"),
            )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr57(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR57.MarkingOfPeriod(Error):
    Previous accounting period is marked(fsa:PrecedingReportingPeriodStartDate), even though it is the first accounting period.
    The company has marked the previous accounting period, even though it is the first accounting period. If the previous accounting period is marked,
    the control expects comparative figures.

    DBA.FR57.ProfitLoss(Error):
    The profit for the year (fsa:ProfitLoss) in the income statement must be filled in

    DBA.FR57.Equity(Error):
    The equity (fsa:Equity) in the balance sheet must be filled in

    DBA.FR57.Assets(Error):
    Assets (fsa:Assets) must be stated and must not be negative

    DBA.FR57.LiabilitiesAndEquity(Error):
    Liabilities (fsa:LiabilitiesAndEquity) must be stated and must not be negative

    DBA.FR57.Equality(Error):
    Assets (fsa:Assets) must equal Liabilities (fsa:LiabilitiesAndEquity)
    """
    currenStartDateFacts =  getFactsWithDimension(val,pluginData.reportingPeriodStartDateQn, pluginData.consolidatedSoloDimensionQn, [pluginData.consolidatedMemberQn, pluginData.soloMemberQn])
    currentEndDateFacts = getFactsWithDimension(val, pluginData.reportingPeriodEndDateQn, pluginData.consolidatedSoloDimensionQn, [pluginData.consolidatedMemberQn, pluginData.soloMemberQn])
    currentGroupedFacts = groupFactsByContextHash(currenStartDateFacts.union(currentEndDateFacts))
    precedingEndDateFacts = getFactsWithDimension(val, pluginData.precedingReportingPeriodEndDateQn, pluginData.consolidatedSoloDimensionQn, [pluginData.consolidatedMemberQn, pluginData.soloMemberQn])
    precedingStartDateFacts = getFactsWithDimension(val, pluginData.precedingReportingPeriodStartDateQn, pluginData.consolidatedSoloDimensionQn, [pluginData.consolidatedMemberQn, pluginData.soloMemberQn])
    precedingGroupedFacts = groupFactsByContextHash(precedingEndDateFacts.union(precedingStartDateFacts))
    currentEndDateFact = None
    currentStartDateFact = None
    precedingStartDateFact = None
    precedingEndDateFact = None
    foundCurrentAssets = None
    foundCurrentLiabilitiesAndEquity = None
    foundPreviousAssets = None
    foundPreviousLiabilitiesAndEquity = None
    assetErrors = []
    equityErrors = []
    equalityErrorPairs = []
    profitLossErrors = []
    liabilitiesAndEquityErrors = []
    negativeAssetFacts = []
    negativeLiabilitiesAndEquityFacts = []
    currentPeriodFound = any(len(facts) == 2 for facts in currentGroupedFacts.values())
    precedingPeriodFound = any(len(facts) == 2 for facts in precedingGroupedFacts.values())
    if precedingPeriodFound and not currentPeriodFound:
        yield Validation.error(
            codes="DBA.FR57.MarkingOfPeriod",
            msg=_("The company has marked the previous accounting period, even though it is the first accounting period."),
        )
    elif currentPeriodFound:
        assetsFacts = getFactsWithoutDimension(val, pluginData.assetsQn)
        equityFacts = getFactsWithoutDimension(val, pluginData.equityQn)
        profitLossFacts = getFactsWithoutDimension(val, pluginData.profitLossQn)
        liabilitiesAndEquityFacts = getFactsWithoutDimension(val, pluginData.liabilitiesAndEquityQn)
        for context, facts in currentGroupedFacts.items():
            if len(facts) == 2:
                for fact in facts:
                    if fact.qname == pluginData.reportingPeriodStartDateQn:
                        currentStartDateFact = fact
                    elif fact.qname == pluginData.reportingPeriodEndDateQn:
                        currentEndDateFact = fact
                if currentEndDateFact is not None and currentStartDateFact is not None:
                    for asset in assetsFacts:
                        if asset.context.endDatetime - datetime.timedelta(days=1) == currentEndDateFact.xValue:
                            foundCurrentAssets = asset
                            if cast(int, asset.xValue) < 0:
                                    negativeAssetFacts.append(asset)
                    for liabilitiesAndEquity in liabilitiesAndEquityFacts:
                        if liabilitiesAndEquity.context.endDatetime - datetime.timedelta(days=1) == currentEndDateFact.xValue:
                            foundCurrentLiabilitiesAndEquity = liabilitiesAndEquity
                            if cast(int, liabilitiesAndEquity.xValue) < 0:
                                negativeLiabilitiesAndEquityFacts.append(liabilitiesAndEquity)
                    foundCurrentEquity = any(
                        equity.context.endDatetime - datetime.timedelta(days=1) == currentEndDateFact.xValue
                        for equity in equityFacts
                    )
                    foundCurrentProfitLoss = any(
                        profitLoss.context.startDatetime == currentStartDateFact.xValue and
                        profitLoss.context.endDatetime - datetime.timedelta(days=1) == currentEndDateFact.xValue
                        for profitLoss in profitLossFacts
                    )
                    if foundCurrentAssets is not None and foundCurrentLiabilitiesAndEquity is not None:
                        if foundCurrentAssets.xValue != foundCurrentLiabilitiesAndEquity.xValue:
                            equalityErrorPairs.append((foundCurrentAssets, foundCurrentLiabilitiesAndEquity))
                    if foundCurrentAssets is None:
                        assetErrors.append(currentEndDateFact.xValue)
                    if foundCurrentEquity is False:
                        equityErrors.append(currentEndDateFact.xValue)
                    if foundCurrentLiabilitiesAndEquity is None:
                        liabilitiesAndEquityErrors.append(currentEndDateFact.xValue)
                    if foundCurrentProfitLoss is False:
                        profitLossErrors.append([currentStartDateFact.xValue, currentEndDateFact.xValue])
        if precedingPeriodFound:
            for context, facts in precedingGroupedFacts.items():
                if len(facts) == 2:
                    for fact in facts:
                        if fact.qname == pluginData.precedingReportingPeriodStartDateQn:
                            precedingStartDateFact = fact
                        elif fact.qname == pluginData.precedingReportingPeriodEndDateQn:
                            precedingEndDateFact = fact
                    if precedingStartDateFact is not None and precedingEndDateFact is not None:
                        for asset in assetsFacts:
                            if asset.context.endDatetime - datetime.timedelta(days=1) == precedingEndDateFact.xValue:
                                foundPreviousAssets = asset
                                if cast(int, asset.xValue) < 0:
                                    negativeAssetFacts.append(asset)
                        for liabilitiesAndEquity in liabilitiesAndEquityFacts:
                            if liabilitiesAndEquity.context.endDatetime - datetime.timedelta(days=1) == precedingEndDateFact.xValue:
                                foundPreviousLiabilitiesAndEquity = liabilitiesAndEquity
                                if cast(int, liabilitiesAndEquity.xValue) < 0:
                                    negativeLiabilitiesAndEquityFacts.append(liabilitiesAndEquity)
                        foundPreviousEquity = any(
                            equity.context.endDatetime - datetime.timedelta(days=1) == precedingEndDateFact.xValue
                            for equity in equityFacts
                        )
                        foundPreviousProfitLoss = any(
                            profitLoss.context.startDatetime == precedingStartDateFact.xValue and
                            profitLoss.context.endDatetime - datetime.timedelta(days=1) == precedingEndDateFact.xValue
                            for profitLoss in profitLossFacts
                        )
                        if foundPreviousAssets is None:
                            assetErrors.append(precedingEndDateFact.xValue)
                        if foundPreviousEquity is False:
                            equityErrors.append(precedingEndDateFact.xValue)
                        if foundPreviousLiabilitiesAndEquity is None:
                            liabilitiesAndEquityErrors.append(precedingEndDateFact.xValue)
                        if foundPreviousProfitLoss is False:
                            profitLossErrors.append([precedingStartDateFact.xValue, precedingEndDateFact.xValue])
    if not len(assetErrors) == 0:
        yield Validation.error(
            codes="DBA.FR57.Assets",
            msg=_("Assets (fsa:Assets) must be stated and must not be negative. "
                  "There is a problem with the reporting period ending: %(periods)s"),
            periods = ", ".join([cast(datetime.datetime, dt).strftime("%Y-%m-%d") for dt in assetErrors])
        )
    if not len(negativeAssetFacts) == 0:
        for fact in negativeAssetFacts:
            yield Validation.error(
                codes="DBA.FR57.NegativeAssets",
                msg=_("Assets (fsa:Assets) must not be negative. "
                      "Assets was tagged with the value: %(factValue)s"),
                factValue = fact.effectiveValue,
                modelObject=fact
            )
    if not len(equalityErrorPairs) == 0:
        for pair in equalityErrorPairs:
            yield Validation.error(
                codes="DBA.FR57.Equality",
                msg=_("The total of Assets (fsa:Assets) must be equal to the total of Liabilities and Equity (fsa:LiabilitiesAndEquity)."
                      "Assets: %(Assets)s  Liabilities and Equity: %(LiabilitiesAndEquity)s"),
                Assets=pair[0].effectiveValue,
                LiabilitiesAndEquity=pair[1].effectiveValue,
                modelObject=pair
            )
    if not len(equityErrors) == 0:
        yield Validation.error(
            codes="DBA.FR57.Equity",
            msg=_("The equity (fsa:Equity) in the balance sheet must be filled in. There is a problem with the reporting period ending: %(periods)s"),
            periods = ", ".join([cast(datetime.datetime, dt).strftime("%Y-%m-%d") for dt in equityErrors])
        )
    if not len(negativeLiabilitiesAndEquityFacts) == 0:
        for fact in negativeLiabilitiesAndEquityFacts:
            yield Validation.error(
                codes="DBA.FR57.NegativeLiabilitiesAndEquity",
                msg=_("Liabilities and Equity (fsa:LiabilitiesAndEquity) must not be negative."
                      "Liabilities and Equity was tagged with the value: %(factValue)s"),
                factValue = fact.effectiveValue,
                modelObject=fact
            )
    if not len(liabilitiesAndEquityErrors) == 0:
        yield Validation.error(
            codes="DBA.FR57.LiabilitiesAndEquity",
            msg=_("Liabilities and equity (fsa:LiabilitiesAndEquity) in the balance sheet must be filled in."
                  "There is a problem with the reporting period ending: %(periods)s"),
            periods = ", ".join([cast(datetime.datetime, dt).strftime("%Y-%m-%d") for dt in liabilitiesAndEquityErrors])
        )
    if not len(profitLossErrors) == 0:
        for profitLossError in profitLossErrors:
            yield Validation.error(
                codes="DBA.FR57.ProfitLoss",
                msg=_("The profit for the year (fsa:ProfitLoss) in the income statement must be filled in."
                      "There is a problem with the reporting periods starting %(start)s and ending: %(end)s"),
                start = profitLossError[0],
                end = profitLossError[1]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr63(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR63: Items in the balance sheet must be less than or equal to the balance sheet total. Assets must be
    less than or equal to the balance sheet total. Applies to both the year's figures and comparative figures.
    """
    modelXbrl = val.modelXbrl
    asset_facts = modelXbrl.factsByQname.get(pluginData.assetsQn, set())
    for asset_fact in asset_facts:
        if asset_fact.xValid >= VALID and isinstance(asset_fact.xValue, decimal.Decimal):
            concepts_in_error = []
            facts_in_error = []
            for balance_sheet_qn in pluginData.balanceSheetQnLessThanOrEqualToAssets:
                balance_sheet_qn_facts = modelXbrl.factsByQname.get(balance_sheet_qn, set())
                for balance_sheet_qn_fact in balance_sheet_qn_facts:
                    if (balance_sheet_qn_fact.xValid >= VALID and
                            isinstance(balance_sheet_qn_fact.xValue, decimal.Decimal) and
                            asset_fact.contextID == balance_sheet_qn_fact.contextID and
                            asset_fact.xValue < balance_sheet_qn_fact.xValue):
                        concepts_in_error.append(balance_sheet_qn.localName)
                        facts_in_error.append(balance_sheet_qn_fact)
            if len(facts_in_error) > 0:
                yield Validation.error(
                    codes='DBA.FR63',
                    msg=_("The annual report contains items in the balance sheet (year's figures or comparison "
                          "figures) which are greater than the balance sheet total(Assets). The following "
                          "fields do not comply: {}").format(concepts_in_error),
                    modelObject=facts_in_error
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr71(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR71: The accounts must not contain negative personnel costs

    Costs must be reported as positive numbers in the XBRL file. It indicates that there is an error in the setup of the XBRL file.
    The following elements are checked:
        • Personnel costs (fsa:EmployeeBenefitsExpense),
        • Salaries (fsa:WagesAndSalaries)
        • Pensions (fsa:PostemploymentBenefitExpense)
        • Other personnel costs (fsa:OtherEmployeeExpense)

    Both on the year's figures and comparative figures."
    """
    modelXbrl = val.modelXbrl
    facts_in_error = []
    for cost_qn in [
        pluginData.employeeBenefitsExpenseQn,
        pluginData.wagesAndSalariesQn,
        pluginData.postemploymentBenefitExpenseQn,
        pluginData.otherEmployeeExpenseQn
    ]:
        facts = modelXbrl.factsByQname.get(cost_qn, set())
        for fact in facts:
            if fact.xValid >= VALID and isinstance(fact.xValue, decimal.Decimal) and fact.xValue < 0:
                facts_in_error.append(fact)
    if len(facts_in_error) > 0:
        yield Validation.warning(
            codes="DBA.FR71",
            msg=_("Costs must be reported as positive numbers in the XBRL file"),
            modelObject=facts_in_error
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr72(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR72: If the value of arr:TypeOfBasisForModifiedOpinionOnFinancialStatementsReview is set to one of the following:
        Grundlag for konklusion med forbehold // Basis for Qualified Opinion
        Grundlag for afkræftende konklusion // Basis for Adverse Opinion
        Grundlag for manglende konklusion // Basis for Disclaimer of Opinion
    then arr:DescriptionsOfQualificationsOfReviewedFinancialStatements must be tagged.
    """
    modelXbrl = val.modelXbrl
    review_facts = modelXbrl.factsByQname.get(pluginData.typeOfBasisForModifiedOpinionOnFinancialStatementsReviewQn, set())
    for review_fact in review_facts:
        if review_fact.xValid >= VALID and review_fact.xValue in [
            pluginData.basisForAdverseOpinionDanish,
            pluginData.basisForAdverseOpinionEnglish,
            pluginData.basisForDisclaimerOpinionDanish,
            pluginData.basisForDisclaimerOpinionEnglish,
            pluginData.basisForQualifiedOpinionDanish,
            pluginData.basisForQualifiedOpinionEnglish,
        ]:
            description_facts = modelXbrl.factsByQname.get(pluginData.descriptionsOfQualificationsOfReviewedFinancialStatementsQn, set())
            if len(description_facts) == 0:
                yield Validation.warning(
                    codes='DBA.FR72',
                    msg=_("DescriptionsOfQualificationsOfReviewedFinancialStatements must be tagged when {} is tagged with the value of {}").format(
                        pluginData.typeOfBasisForModifiedOpinionOnFinancialStatementsReviewQn.localName,
                        review_fact.xValue
                    ),
                    modelObject=review_fact
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr73(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR73: If arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsExtendedReview is tagged then one of the following concepts MUST also be tagged:
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCriminalCodeAndFiscalTaxAndSubsidyLegislationExtendedReview
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCompaniesActOrEquivalentLegislationThatTheCompanyIsSubjectToExtendedReview
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyLegislationOnFinancialReportingInApplication
    """
    modelXbrl = val.modelXbrl
    indicatorFacts = modelXbrl.factsByQname.get(pluginData.reportingResponsibilitiesOnApprovedAuditorsReportsExtendedReviewQn, set())
    if len(indicatorFacts) > 0:
        for qname in pluginData.reportingObligationQns:
            facts = modelXbrl.factsByQname.get(qname, set())
            if len(facts) > 0:
                return
        yield Validation.warning(
            codes='DBA.FR73',
            msg=_("When the field ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsExtendedReview is completed"
                  "one or more of the sub-items below must be indicated: "
                  "ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCriminalCodeAndFiscalTaxAndSubsidyLegislationExtendedReview "
                  "ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCompaniesActOrEquivalentLegislationThatTheCompanyIsSubjectToExtendedReview "
                  "ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyLegislationOnFinancialReportingInApplication."),
        )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr74(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR74a:Provisions [hierarchy:fsa:Provisions] and underlying fields must each be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity).
    DBA.FR74b: Liabilities (fsa:LiabilitiesOtherThanProvisions) must be less than or equal to total assets (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity).
    """
    groupedFacts = getFactsGroupedByContextId(val.modelXbrl, pluginData.equityQn, pluginData.liabilitiesAndEquityQn, pluginData.provisionsQn, pluginData.liabilitiesOtherThanProvisionsQn)
    for contextID, facts in groupedFacts.items():
        equityFact = None
        liabilityFact = None
        liabilityOtherFact = None
        provisionFact = None
        for fact in facts:
            if fact.qname == pluginData.equityQn and fact.unit.id == DANISH_CURRENCY_ID:
                equityFact = fact
            elif fact.qname == pluginData.liabilitiesQn and fact.unit.id == DANISH_CURRENCY_ID:
                liabilityFact = fact
            elif fact.qname == pluginData.provisionsQn and fact.unit.id == DANISH_CURRENCY_ID:
                provisionFact = fact
            elif fact.qname == pluginData.liabilitiesOtherThanProvisionsQn and fact.unit.id == DANISH_CURRENCY_ID:
                liabilityOtherFact = fact
        if equityFact is not None and liabilityFact is not None and provisionFact is not None and equityFact.xValid >= VALID and liabilityFact.xValid >= VALID and provisionFact.xValid >= VALID:
            if not cast(decimal.Decimal, liabilityFact.xValue) - cast(decimal.Decimal, equityFact.xValue) >= cast(decimal.Decimal, provisionFact.xValue) - ROUNDING_MARGIN:
                yield Validation.error(
                    codes="DBA.FR74a",
                    msg=_("Provisions (fsa:Provisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity)."
                          "LiabilitiesAndEquity: %(liabilities)s, Equity: %(equity)s, Provisions: %(provisions)s"),
                    equity=equityFact.effectiveValue,
                    liabilities=liabilityFact.effectiveValue,
                    provisions=provisionFact.effectiveValue,
                    modelObject=[equityFact, liabilityFact, provisionFact]
                )
        if equityFact is not None and liabilityOtherFact is not None and liabilityFact is not None and equityFact.xValid >= VALID and liabilityFact.xValid >= VALID and liabilityOtherFact.xValid >= VALID:
            if not cast(decimal.Decimal, liabilityFact.xValue) - cast(decimal.Decimal, equityFact.xValue) >= cast(decimal.Decimal, liabilityOtherFact.xValue) - ROUNDING_MARGIN:
                yield Validation.error(
                    codes="DBA.FR74b",
                    msg=_("Liabilities (fsa:LiabilitiesOtherThanProvisions) must be less than or equal to total assets (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity)."
                          "LiabilitiesAndEquity: %(liabilities)s, Equity: %(equity)s, LiabilitiesOtherThanProvisions: %(liabilityOther)s"),
                    equity=equityFact.effectiveValue,
                    liabilityOther=liabilityOtherFact.effectiveValue,
                    liabilities=liabilityFact.effectiveValue,
                    modelObject=[equityFact, liabilityFact, liabilityOtherFact]
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr75(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR75: The company must provide information on the number of employees. The rule is activated if personnel costs (fsa:EmployeeBenefitsExpense) or salaries (fsa:WagesAndSalaries) are greater
    than DKK 200,000, and no number of employees (fsa:AverageNumberOfEmployees) has been specified.
    """
    groupedFacts = getFactsGroupedByContextId(val.modelXbrl, pluginData.employeeBenefitsExpenseQn, pluginData.wagesAndSalariesQn, pluginData.averageNumberOfEmployeesQn)
    for contextID, facts in groupedFacts.items():
        benefitsFact = None
        wagesFact = None
        employeesFact = None
        for fact in facts:
            if fact.qname == pluginData.employeeBenefitsExpenseQn and fact.unit.id == DANISH_CURRENCY_ID and fact.xValid >= VALID and cast(decimal.Decimal, fact.xValue) >= PERSONNEL_EXPENSE_THRESHOLD:
                benefitsFact = fact
            elif fact.qname == pluginData.wagesAndSalariesQn and fact.unit.id == DANISH_CURRENCY_ID and fact.xValid >= VALID and cast(decimal.Decimal, fact.xValue) >= PERSONNEL_EXPENSE_THRESHOLD:
                wagesFact = fact
            elif fact.qname == pluginData.averageNumberOfEmployeesQn and fact.xValid >= VALID and cast(decimal.Decimal, fact.xValue) > 0:
                employeesFact = fact
        if (benefitsFact is not None or wagesFact is not None) and employeesFact is None:
            yield Validation.error(
                codes="DBA.FR75",
                msg=_("The company must provide information on the number of employees. The rule is activated if personnel costs (fsa:EmployeeBenefitsExpense) "
                      "or salaries (fsa:WagesAndSalaries) are greater than DKK 200,000, and no number of employees (fsa:AverageNumberOfEmployees) has been specified."),
                modelObject=[benefitsFact, wagesFact]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr77(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR77b: Long-term liabilities (fsa:LongtermLiabilitiesOtherThanProvisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity).
    DBA.FR77b: Short-term liabilities (fsa:ShorttermLiabilitiesOtherThanProvisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity).
    """
    groupedFacts = getFactsGroupedByContextId(val.modelXbrl, pluginData.equityQn, pluginData.liabilitiesAndEquityQn, pluginData.longtermLiabilitiesOtherThanProvisionsQn, pluginData.shorttermLiabilitiesOtherThanProvisionsQn)
    for contextID, facts in groupedFacts.items():
        equityFact = None
        liabilityFact = None
        longLiabilityFact = None
        shortLiabilityFact = None
        for fact in facts:
            if fact.qname == pluginData.equityQn and fact.unit.id == DANISH_CURRENCY_ID:
                equityFact = fact
            elif fact.qname == pluginData.liabilitiesQn and fact.unit.id == DANISH_CURRENCY_ID:
                liabilityFact = fact
            elif fact.qname == pluginData.longtermLiabilitiesOtherThanProvisionsQn and fact.unit.id == DANISH_CURRENCY_ID:
                longLiabilityFact = fact
            elif fact.qname == pluginData.shorttermLiabilitiesOtherThanProvisionsQn and fact.unit.id == DANISH_CURRENCY_ID:
                shortLiabilityFact = fact
        if equityFact is not None and liabilityFact is not None and longLiabilityFact is not None and equityFact.xValid >= VALID and liabilityFact.xValid >= VALID and longLiabilityFact.xValid >= VALID:
            if not cast(decimal.Decimal, liabilityFact.xValue) - cast(decimal.Decimal, equityFact.xValue) >= cast(decimal.Decimal, longLiabilityFact.xValue) - ROUNDING_MARGIN:
                yield Validation.error(
                    codes="DBA.FR77a",
                    msg=_("Long-term liabilities (fsa:LongtermLiabilitiesOtherThanProvisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity)."
                          "LiabilitiesAndEquity: %(liabilities)s, Equity: %(equity)s, LongtermLiabilitiesOtherThanProvisions: %(longLiabilities)s"),
                    equity=equityFact.effectiveValue,
                    liabilities=liabilityFact.effectiveValue,
                    longLiabilities=longLiabilityFact.effectiveValue,
                    modelObject=[equityFact, liabilityFact, longLiabilityFact]
                )
        if equityFact is not None and liabilityFact is not None and shortLiabilityFact is not None and equityFact.xValid >= VALID and liabilityFact.xValid >= VALID and shortLiabilityFact.xValid >= VALID:
            if not cast(decimal.Decimal, liabilityFact.xValue) - cast(decimal.Decimal, equityFact.xValue) >= cast(decimal.Decimal, shortLiabilityFact.xValue) - ROUNDING_MARGIN:
                yield Validation.error(
                    codes="DBA.FR77b",
                    msg=_("Short-term liabilities (fsa:ShorttermLiabilitiesOtherThanProvisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity)."
                          "LiabilitiesAndEquity: %(liabilities)s, Equity: %(equity)s, ShorttermLiabilitiesOtherThanProvisions: %(shortLiabilities)s"),
                    equity=equityFact.effectiveValue,
                    liabilities=liabilityFact.effectiveValue,
                    shortLiabilities=shortLiabilityFact.effectiveValue,
                    modelObject=[equityFact, liabilityFact, shortLiabilityFact]
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr81(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR81: The language used must be stated. There must be at least one fact with either the Danish
    (`da`) or English (`en`) `lang` attribute in the digital file (the XBRL file or the IXBRL file).

    Implementation: Check all facts for at least one `lang` attribute that must be either `da` or `en`.
    """
    has_valid_lang = any(fact.xmlLang in {'da', 'en'} for fact in val.modelXbrl.facts)
    if not has_valid_lang:
        yield Validation.error(
            codes="DBA.FR81",
            msg=_("The digital annual report does not contain a technical indication of the language used. There "
                  "must be at least one fact, with either the Danish ('da') or English ('en') language attribute."),
            modelObject=[val.modelXbrl.modelDocument]
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr87(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR87:  InlineXBRL must not link to external CSS. The IXBRL file must have all CSS inline.
    """
    modelXbrl = val.modelXbrl
    _xhtmlNs = "{{{}}}".format(xhtml)
    _xhtmlNsLen = len(_xhtmlNs)
    if hasattr(modelXbrl, "ixdsHtmlElements"):
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements: # ix root elements for all ix docs in IXDS
            ixNStag = ixdsHtmlRootElt.modelDocument.ixNStag
            ixTags = set(ixNStag + ln for ln in ("nonNumeric", "nonFraction", "references", "relationship"))
        ixTargets = set()
        for ixdsHtmlRootElt in modelXbrl.ixdsHtmlElements:
            for elt in ixdsHtmlRootElt.iter():
                eltTag = elt.tag
                if eltTag in ixTags:
                    ixTargets.add( elt.get("target") )
                else:
                    if eltTag.startswith(_xhtmlNs):
                        eltTag = eltTag[_xhtmlNsLen:]
                        if eltTag == "link" and elt.get("type") == "text/css":
                            yield Validation.error(
                                codes='DBA.FR87',
                                msg=_("CSS must be embedded in the inline XBRL document. The document contains a link to an external CSS file."),
                                modelObject=elt,
                            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr89(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR89: If ClassOfReportingEntity is one of the following values:

    Regnskabsklasse C, mellemstor virksomhed // Reporting class C, medium-size enterprise
    Regnskabsklasse C, stor virksomhed // Reporting class C, large enterprise
    Regnskabsklasse D // Reporting class D
    Then TypeOfAuditorAssistance should be: Revisionspåtegning // Auditor's report on audited financial statements
    """
    modelXbrl = val.modelXbrl
    auditorFacts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn)
    if auditorFacts is not None:
        for auditorFact in auditorFacts:
            if auditorFact.xValid >= VALID and auditorFact.xValue in [
                pluginData.auditedFinancialStatementsDanish,
                pluginData.auditedFinancialStatementsEnglish
            ]:
                return
    classFacts = []
    facts = modelXbrl.factsByQname.get(pluginData.classOfReportingEntityQn)
    if facts is not None:
        for fact in facts:
            if fact.xValid >= VALID:
                if fact.xValue in [
                    pluginData.reportingClassCLargeDanish,
                    pluginData.reportingClassCLargeEnglish,
                    pluginData.reportingClassCMediumDanish,
                    pluginData.reportingClassCMediumEnglish,
                    pluginData.reportingClassDDanish,
                    pluginData.reportingClassDEnglish,
                ]:
                    classFacts.append(fact)
        if len(classFacts) > 0:
            yield Validation.error(
                codes='DBA.FR89',
                msg=_("TypeOfAuditorAssistance should be {} or {} when {} is tagged with the value of {}.").format(
                    pluginData.auditedFinancialStatementsDanish,
                    pluginData.auditedFinancialStatementsEnglish,
                    pluginData.classOfReportingEntityQn.localName,
                    classFacts[0].xValue
                ),
                modelObject=classFacts[0]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr92(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR92: Information is missing on the auditor's signature date.

    The auditor's signature date must be provided when (fsa:TypeOfAuditorAssistance) is
    tagged with one of the following values:
    - (Revisionspåtegning)  / (Auditor's report on audited financial statements)
    - (Erklæring om udvidet gennemgang) / (Auditor's report on extended review)
    - (Den uafhængige revisors erklæringer (review)) / (The independent auditor's reports (Review))
    - (Andre erklæringer med sikkerhed) / (The independent auditor's reports (Other assurance Reports))
    - (Andre erklæringer uden sikkerhed) / (Auditor's reports (Other non-assurance reports))
    """
    modelXbrl = val.modelXbrl
    facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for fact in facts:
        if fact.xValid >= VALID:
            if fact.xValue in [
                pluginData.auditedFinancialStatementsDanish,
                pluginData.auditedFinancialStatementsEnglish,
                pluginData.auditedExtendedReviewDanish,
                pluginData.auditedExtendedReviewEnglish,
                pluginData.independentAuditorsReportDanish,
                pluginData.independentAuditorsReportEnglish,
                pluginData.auditedAssuranceReportsDanish,
                pluginData.auditedAssuranceReportsEnglish,
                pluginData.auditedNonAssuranceReportsDanish,
                pluginData.auditedNonAssuranceReportsEnglish,
            ]:
                signature_facts = modelXbrl.factsByQname.get(pluginData.signatureOfAuditorsDateQn, set())
                if len(signature_facts) == 0:
                    yield Validation.error(
                        codes='DBA.FR92',
                        msg=_("SignatureOfAuditorsDate must be tagged when {} is tagged with the value of {}").format(
                            pluginData.typeOfAuditorAssistanceQn.localName,
                            fact.xValue
                        ),
                        modelObject=fact
                    )
