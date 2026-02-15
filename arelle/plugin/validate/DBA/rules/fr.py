"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections import defaultdict

import datetime
import decimal
from collections.abc import Iterable
from lxml import etree
from typing import Any, cast

from arelle import ValidateDuplicateFacts
from arelle.ModelDocumentType import ModelDocumentType
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelValue import QName
from arelle.ValidateDuplicateFacts import DuplicateType
from arelle.XbrlConst import xhtml
from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.Contexts import ContextHashKey
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from . import errorOnDateFactComparison, getFactsWithDimension, getFactsGroupedByContextId, getFactsWithoutDimension, groupFactsByContextHash, \
    minimumRequiredFactsFound, consolidatedDimensionExists
from ..PluginValidationDataExtension import PluginValidationDataExtension
from ..ValidationPluginExtension import DANISH_CURRENCY_ID, ROUNDING_MARGIN, PERSONNEL_EXPENSE_THRESHOLD, REQUIRED_DISCLOSURE_OF_EQUITY_FACTS, REQUIRED_STATEMENT_OF_CHANGES_IN_EQUITY_FACTS
from ..DisclosureSystems import (ARL_MULTI_TARGET_DISCLOSURE_SYSTEMS, STAND_ALONE_DISCLOSURE_SYSTEMS,
                                 ARL_DISCLOSURE_SYSTEMS, ARL_2022_PREVIEW, ARL_2024_PREVIEW,
                                 ARL_2024_MULTI_TARGET_PREVIEW, ARL_2025_PREVIEW, ARL_2025_MULTI_TARGET_PREVIEW)

_: TypeGetText

@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
)
def rule_fr24(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR24: arr:DescriptionOfQualificationsOfAuditedFinancialStatements must not contain the following text:
            - 'har ikke givet anledning til forbehold'
            - 'has not given rise to reservations'
        when cmn:TypeOfAuditorAssistance has one of the following values:

        2022 or 2024 Values:
            - Revisionspåtegning
            - Auditor's report on audited financial statements

        2025+ Values:
            - Den uafhængige revisors erklæring
            - Independent Auditor’s Report
    """
    modelXbrl = val.modelXbrl
    if val.disclosureSystem.name in [ARL_2022_PREVIEW, ARL_2024_PREVIEW, ARL_2024_MULTI_TARGET_PREVIEW]:
        validAuditorFactValues = [
            pluginData.auditedFinancialStatementsDanish,
            pluginData.auditedFinancialStatementsEnglish
        ]
    else:
        validAuditorFactValues = [
            pluginData.independentAuditorsReportDanish,
            pluginData.independentAuditorsReportEnglish,
        ]
    type_of_auditors_assistance_facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for auditor_fact in type_of_auditors_assistance_facts:
        if auditor_fact.xValid >= VALID and auditor_fact.xValue in validAuditorFactValues:
            description_facts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfAuditedFinancialStatementsQn, set())
            for description_fact in description_facts:
                if description_fact.xValid >= VALID:
                    for text in pluginData.hasNotGivenRiseToReservationsText:
                        if text in str(description_fact.xValue):
                            yield Validation.error(
                                codes="DBA.FR24",
                                msg=_("The value of DescriptionOfQualificationsOfAuditedFinancialStatements must not "
                                      "contain the text: \'{}\', when TypeOfAuditorAssistance is set to \'{}\' "
                                      "or \'{}\'").format(
                                    text,
                                    validAuditorFactValues[0],
                                    validAuditorFactValues[1]
                                ),
                                modelObject=description_fact
                            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
)
def rule_fr25(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR25: arr:DescriptionOfQualificationsOfFinancialStatementsExtendedReview must not contain the following text:
            - 'har ikke givet anledning til forbehold'
            - 'has not given rise to reservations'
        When cmn:TypeOfAuditorAssistance has the following values:

        2022 or 2024 Values:
            - Erklæring om udvidet gennemgang
            - Auditor's report on extended review
        2025+ Values:
            - Den uafhængige revisors erklæring om udvidet gennemgang
            - Independent Practitioner’s Extended Review Report
    """
    modelXbrl = val.modelXbrl
    if val.disclosureSystem.name in [ARL_2022_PREVIEW, ARL_2024_PREVIEW, ARL_2024_MULTI_TARGET_PREVIEW]:
        validAuditorFactValues = [
            pluginData.auditedExtendedReviewDanish,
            pluginData.auditedExtendedReviewEnglish
        ]
    else:
        validAuditorFactValues = [
            pluginData.independentPractitionersExtendedReviewReportDanish,
            pluginData.independentPractitionersExtendedReviewReportEnglish,
        ]
    type_of_auditors_assistance_facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for auditor_fact in type_of_auditors_assistance_facts:
        if auditor_fact.xValid >= VALID and auditor_fact.xValue in validAuditorFactValues:
            description_facts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfFinancialStatementsExtendedReviewQn, set())
            for description_fact in description_facts:
                if description_fact.xValid >= VALID:
                    for text in pluginData.hasNotGivenRiseToReservationsText:
                        if text in str(description_fact.xValue):
                            yield Validation.error(
                                codes="DBA.FR25",
                                msg=_("The value of DescriptionOfQualificationsOfFinancialStatementsExtendedReview must not "
                                      "contain the text: \'{}\', when TypeOfAuditorAssistance is set to \'{}\' or \'{}\'").format(
                                    text,
                                    validAuditorFactValues[0],
                                    validAuditorFactValues[1]
                                ),
                                modelObject=description_fact
                            )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    noDimensionFacts = set()
    consolidatedDimensionFacts = set()
    checkConsolidated = consolidatedDimensionExists(modelXbrl, pluginData.consolidatedSoloDimensionQn)
    for concept_qn in pluginData.accountingPolicyConceptQns:
        facts = modelXbrl.factsByQname.get(concept_qn, set())
        for fact in facts:
            if fact.xValid >= VALID and not fact.isNil:
                if not fact.context.scenDimValues:
                    noDimensionFacts.add(fact)
                if pluginData.consolidatedSoloDimensionQn in [dim.qname for dim in fact.context.scenDimValues.keys()]:
                    consolidatedDimensionFacts.add(fact)
    if not checkConsolidated and len(noDimensionFacts) == 0:
        yield Validation.error(
            codes="DBA.FR35.noDimension",
            msg=_("The annual report does not contain information on applied accounting practices. Please tag one of the following elements without a dimension: {}").format(
                [qn.localName for qn in pluginData.accountingPolicyConceptQns]
            ),
            modelObject=val.modelXbrl.modelDocument
        )
    if checkConsolidated and len(consolidatedDimensionFacts) == 0:
        yield Validation.error(
            codes="DBA.FR35.consolidatedSoloDimension",
            msg=_("The annual report does not contain information on applied accounting practices. Please tag one of the following elements with the ConsolidatedSoloDimension: {}").format(
                [qn.localName for qn in pluginData.accountingPolicyConceptQns]
            ),
            modelObject=val.modelXbrl.modelDocument
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
            msg=_("Annual reports with a start date of 1/1 2016 or later must not use the fields: "
                  "'Extraordinary profit before tax', 'Extraordinary income', 'Extraordinary costs'."),
            modelObject=foundFacts
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=[
        ARL_2022_PREVIEW,
        ARL_2024_PREVIEW,
        ARL_2024_MULTI_TARGET_PREVIEW,
    ],
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
                pluginData.independentAuditorsReportReviewDanish,
                pluginData.independentAuditorsReportReviewEnglish,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    currentStartDateFacts = getFactsWithDimension(val, pluginData.reportingPeriodStartDateQn, pluginData.consolidatedSoloDimensionQn, [pluginData.consolidatedMemberQn, pluginData.soloMemberQn])
    currentEndDateFacts = getFactsWithDimension(val, pluginData.reportingPeriodEndDateQn, pluginData.consolidatedSoloDimensionQn, [pluginData.consolidatedMemberQn, pluginData.soloMemberQn])
    currentGroupedFacts = groupFactsByContextHash(currentStartDateFacts.union(currentEndDateFacts))
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
        for facts in currentGroupedFacts.values():
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
                msg=_("The total of Assets (fsa:Assets) must be equal to the total of Liabilities and Equity (fsa:LiabilitiesAndEquity). "
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
                msg=_("Liabilities and Equity (fsa:LiabilitiesAndEquity) must not be negative. "
                      "Liabilities and Equity was tagged with the value: %(factValue)s"),
                factValue = fact.effectiveValue,
                modelObject=fact
            )
    if not len(liabilitiesAndEquityErrors) == 0:
        yield Validation.error(
            codes="DBA.FR57.LiabilitiesAndEquity",
            msg=_("Liabilities and equity (fsa:LiabilitiesAndEquity) in the balance sheet must be filled in. "
                  "There is a problem with the reporting period ending: %(periods)s"),
            periods = ", ".join([cast(datetime.datetime, dt).strftime("%Y-%m-%d") for dt in liabilitiesAndEquityErrors])
        )
    if not len(profitLossErrors) == 0:
        for profitLossError in profitLossErrors:
            yield Validation.error(
                codes="DBA.FR57.ProfitLoss",
                msg=_("The profit for the year (fsa:ProfitLoss) in the income statement must be filled in. "
                      "There is a problem with the reporting periods starting %(start)s and ending: %(end)s"),
                start = profitLossError[0],
                end = profitLossError[1]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
)
def rule_fr58(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR58: If arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportAudit is tagged then one of the following concepts MUST also be tagged:
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCriminalCodeAndFiscalTaxAndSubsidyLegislationAudit
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCompaniesActOrEquivalentLegislationThatTheCompanyIsSubjectToAudit
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyLegislationOnFinancialReportingIncludingAccountingAndStorageOfAccountingRecordsAudit
    arr:ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyOtherMattersAudit

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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
)
def rule_fr59(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR59: arr:DescriptionOfQualificationsOfAuditedFinancialStatements must be filled in
              when cmn:TypeOfAuditorAssistance has one of the following values:

              2022 or 2024 Values:
                - Revisionspåtegning
                - Auditor's report on audited financial statements

              2025+ Values:
                - Den uafhængige revisors erklæring
                - Independent Auditor’s Report
    """
    modelXbrl = val.modelXbrl
    if val.disclosureSystem.name in [ARL_2022_PREVIEW, ARL_2024_PREVIEW, ARL_2024_MULTI_TARGET_PREVIEW]:
        validAuditorFactValues = [
            pluginData.auditedFinancialStatementsDanish,
            pluginData.auditedFinancialStatementsEnglish
        ]
    else:
        validAuditorFactValues = [
            pluginData.independentAuditorsReportDanish,
            pluginData.independentAuditorsReportEnglish,
        ]
    noDimensionDescriptionFacts = []
    consolidatedDescriptionFacts = []
    descriptionFacts = modelXbrl.factsByQname.get(pluginData.descriptionOfQualificationsOfAuditedFinancialStatementsQn, set())
    for dFact in descriptionFacts:
        if not dFact.context.scenDimValues:
            noDimensionDescriptionFacts.append(dFact)
        if pluginData.consolidatedSoloDimensionQn in [dim.qname for dim in dFact.context.scenDimValues.keys()]:
            consolidatedDescriptionFacts.append(dFact)
    checkConsolidated = consolidatedDimensionExists(modelXbrl, pluginData.consolidatedSoloDimensionQn)
    noDimensionIndicatorFacts = []
    consolidatedIndicatorFacts = []
    auditorFacts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for aFact in auditorFacts:
        if aFact.xValid >= VALID and aFact.xValue in validAuditorFactValues:
            if not aFact.context.scenDimValues:
                noDimensionIndicatorFacts.append(aFact)
            if pluginData.consolidatedSoloDimensionQn in [dim.qname for dim in aFact.context.scenDimValues.keys()]:
                consolidatedIndicatorFacts.append(aFact)
    if not checkConsolidated and len(noDimensionIndicatorFacts) > 0 and len(noDimensionDescriptionFacts) == 0:
        yield Validation.error(
            codes='DBA.FR59.noDimension',
            msg=_("DescriptionOfQualificationsOfAuditedFinancialStatement must be tagged without dimensions when {} is tagged with the value of {}").format(
                pluginData.typeOfAuditorAssistanceQn.localName,
                noDimensionIndicatorFacts[0].xValue),
            modelObject=noDimensionIndicatorFacts[0])
    if checkConsolidated and len(consolidatedIndicatorFacts) > 0 and len(consolidatedDescriptionFacts) == 0:
        yield Validation.error(
            codes='DBA.FR59.consolidatedSoloDimension',
            msg=_("DescriptionOfQualificationsOfAuditedFinancialStatement must be tagged with ConsolidatedSoloDimension when {} is tagged with the value of {}").format(
                pluginData.typeOfAuditorAssistanceQn.localName,
                consolidatedIndicatorFacts[0].xValue),
            modelObject=consolidatedIndicatorFacts[0])


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
            msg=_("When the field ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsExtendedReview is completed "
                  "one or more of the sub-items below must be indicated: "
                  "ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCriminalCodeAndFiscalTaxAndSubsidyLegislationExtendedReview "
                  "ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyTheCompaniesActOrEquivalentLegislationThatTheCompanyIsSubjectToExtendedReview "
                  "ReportingResponsibilitiesAccordingToTheDanishExecutiveOrderOnApprovedAuditorsReportsEspeciallyLegislationOnFinancialReportingInApplication."),
        )



@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
            if fact.qname == pluginData.equityQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                equityFact = fact
            elif fact.qname == pluginData.liabilitiesQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                liabilityFact = fact
            elif fact.qname == pluginData.provisionsQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                provisionFact = fact
            elif fact.qname == pluginData.liabilitiesOtherThanProvisionsQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                liabilityOtherFact = fact
        if equityFact is not None and liabilityFact is not None and provisionFact is not None and equityFact.xValid >= VALID and liabilityFact.xValid >= VALID and provisionFact.xValid >= VALID:
            if not cast(decimal.Decimal, liabilityFact.xValue) - cast(decimal.Decimal, equityFact.xValue) >= cast(decimal.Decimal, provisionFact.xValue) - ROUNDING_MARGIN:
                yield Validation.error(
                    codes="DBA.FR74a",
                    msg=_("Provisions (fsa:Provisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity). "
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
                    msg=_("Liabilities (fsa:LiabilitiesOtherThanProvisions) must be less than or equal to total assets (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity). "
                          "LiabilitiesAndEquity: %(liabilities)s, Equity: %(equity)s, LiabilitiesOtherThanProvisions: %(liabilityOther)s"),
                    equity=equityFact.effectiveValue,
                    liabilityOther=liabilityOtherFact.effectiveValue,
                    liabilities=liabilityFact.effectiveValue,
                    modelObject=[equityFact, liabilityFact, liabilityOtherFact]
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
            if fact.qname == pluginData.employeeBenefitsExpenseQn and fact.unit.id.upper() == DANISH_CURRENCY_ID and fact.xValid >= VALID and cast(decimal.Decimal, fact.xValue) >= PERSONNEL_EXPENSE_THRESHOLD:
                benefitsFact = fact
            elif fact.qname == pluginData.wagesAndSalariesQn and fact.unit.id.upper() == DANISH_CURRENCY_ID and fact.xValid >= VALID and cast(decimal.Decimal, fact.xValue) >= PERSONNEL_EXPENSE_THRESHOLD:
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
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
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
            if fact.qname == pluginData.equityQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                equityFact = fact
            elif fact.qname == pluginData.liabilitiesQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                liabilityFact = fact
            elif fact.qname == pluginData.longtermLiabilitiesOtherThanProvisionsQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                longLiabilityFact = fact
            elif fact.qname == pluginData.shorttermLiabilitiesOtherThanProvisionsQn and fact.unit.id.upper() == DANISH_CURRENCY_ID:
                shortLiabilityFact = fact
        if equityFact is not None and liabilityFact is not None and longLiabilityFact is not None and equityFact.xValid >= VALID and liabilityFact.xValid >= VALID and longLiabilityFact.xValid >= VALID:
            if not cast(decimal.Decimal, liabilityFact.xValue) - cast(decimal.Decimal, equityFact.xValue) >= cast(decimal.Decimal, longLiabilityFact.xValue) - ROUNDING_MARGIN:
                yield Validation.error(
                    codes="DBA.FR77a",
                    msg=_("Long-term liabilities (fsa:LongtermLiabilitiesOtherThanProvisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity). "
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
                    msg=_("Short-term liabilities (fsa:ShorttermLiabilitiesOtherThanProvisions) must be less than or equal to the balance sheet total (fsa:LiabilitiesAndEquity) minus equity (fsa:Equity). "
                          "LiabilitiesAndEquity: %(liabilities)s, Equity: %(equity)s, ShorttermLiabilitiesOtherThanProvisions: %(shortLiabilities)s"),
                    equity=equityFact.effectiveValue,
                    liabilities=liabilityFact.effectiveValue,
                    shortLiabilities=shortLiabilityFact.effectiveValue,
                    modelObject=[equityFact, liabilityFact, shortLiabilityFact]
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
    disclosureSystems=ARL_MULTI_TARGET_DISCLOSURE_SYSTEMS,
)
def rule_fr82(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR82: This control blocks reporting in XBRL and thus only allows reporting with inlineXBRL for DK ESEF.
    """
    if (val.modelXbrl.modelDocument is not None and
            val.modelXbrl.modelDocument.type not in [ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET]):
        yield Validation.error(
            codes="DBA.FR82",
            msg=_("The digital annual report must be reported in inlineXBRL for DK ESEF."),
            modelObject=[val.modelXbrl.modelDocument]
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr83(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR83: This control blocks reporting in XBRL and thus only allows reporting with inlineXBRL for DK GAAP.
    """
    if (val.modelXbrl.modelDocument is not None and
            val.modelXbrl.modelDocument.type not in [ModelDocumentType.INLINEXBRL, ModelDocumentType.INLINEXBRLDOCUMENTSET]):
        yield Validation.error(
            codes="DBA.FR83",
            msg=_("The digital annual report must be reported in inlineXBRL for DK GAAP."),
            modelObject=[val.modelXbrl.modelDocument]
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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
            for elt in ixdsHtmlRootElt.iter(etree.Element):
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
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
)
def rule_fr89(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR89: If ClassOfReportingEntity is one of the following values:

    2022 or 2024 Values:
        Regnskabsklasse C, mellemstor virksomhed // Reporting class C, medium-size enterprise
        Regnskabsklasse C, stor virksomhed // Reporting class C, large enterprise
        Regnskabsklasse D // Reporting class D
        Then TypeOfAuditorAssistance should be: Revisionspåtegning // Auditor's report on audited financial statements

    2025+ Values:
        Regnskabsklasse C, mellemstor virksomhed // Reporting class C, medium-size enterprise
        regnskabsklasse C, mellemstor virksomhed // reporting class C, medium-size enterprise
        Regnskabsklasse C, stor virksomhed // Reporting class C, large enterprise
        regnskabsklasse C, stor virksomhed // reporting class C, large enterprise
        Regnskabsklasse D // Reporting class D
        regnskabsklasse D // reporting class D
        Then TypeOfAuditorAssistance should be: Den uafhængige revisors erklæring // Independent Auditor’s Report
    """
    if pluginData.isAnnualReport(val.modelXbrl):
        if val.disclosureSystem.name in [ARL_2022_PREVIEW, ARL_2024_PREVIEW, ARL_2024_MULTI_TARGET_PREVIEW]:
            validAuditorFactValues = [
                pluginData.auditedFinancialStatementsDanish,
                pluginData.auditedFinancialStatementsEnglish
            ]
        else:
            validAuditorFactValues = [
                pluginData.independentAuditorsReportDanish,
                pluginData.independentAuditorsReportEnglish,
            ]
        auditorFacts = val.modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
        for auditorFact in auditorFacts:
            if auditorFact.xValid >= VALID and auditorFact.xValue in validAuditorFactValues:
                return
        classFacts = []
        facts = val.modelXbrl.factsByQname.get(pluginData.classOfReportingEntityQn, set())
        for fact in facts:
            if fact.xValid >= VALID and fact.xValue in [
                pluginData.reportingClassCLargeDanish,
                pluginData.reportingClassCLargeEnglish,
                pluginData.reportingClassCLargeLowercaseDanish,
                pluginData.reportingClassCLargeLowercaseEnglish,
                pluginData.reportingClassCMediumDanish,
                pluginData.reportingClassCMediumEnglish,
                pluginData.reportingClassCMediumLowercaseDanish,
                pluginData.reportingClassCMediumLowercaseEnglish,
                pluginData.reportingClassDDanish,
                pluginData.reportingClassDEnglish,
                pluginData.reportingClassDLowercaseDanish,
                pluginData.reportingClassDLowercaseEnglish
            ]:
                classFacts.append(fact)
        if len(classFacts) > 0:
            yield Validation.error(
                codes='DBA.FR89',
                msg=_("TypeOfAuditorAssistance should be {} or {} when {} is tagged with the value of {}.").format(
                    validAuditorFactValues[0],
                    validAuditorFactValues[1],
                    pluginData.classOfReportingEntityQn.localName,
                    classFacts[0].xValue
                ),
                modelObject=classFacts[0]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
)
def rule_fr91(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR91: If the annual report contains information about both the general meeting date
    (gsd:DateOfGeneralMeeting) and the annual accounts meeting date (gsd:DateOfApprovalOfAnnualReport), the values must be the same.
    """
    if pluginData.isAnnualReport(val.modelXbrl):
        approvalOfReportFact = None
        generalMeetingFact = None
        approvalFacts = (val.modelXbrl.factsByQname.get(pluginData.dateOfApprovalOfAnnualReportQn, set()))
        if len(approvalFacts) > 0:
            approvalOfReportFact = next(iter(approvalFacts), None)
        meetingFacts = val.modelXbrl.factsByQname.get(pluginData.dateOfGeneralMeetingQn, set())
        if len(meetingFacts) > 0:
            generalMeetingFact = next(iter(meetingFacts), None)
        if generalMeetingFact is not None and generalMeetingFact.xValid >= VALID and approvalOfReportFact is not None and approvalOfReportFact.xValid >= VALID and generalMeetingFact.xValue != approvalOfReportFact.xValue:
            yield Validation.error(
                codes='DBA.FR91',
                msg=_("The annual report contains information about both the general meeting date (gsd:DateOfGeneralMeeting) and the annual accounts meeting date (gsd:DateOfApprovalOfAnnualReport), the values must be the same."),
                modelObject=[generalMeetingFact, approvalOfReportFact]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ARL_DISCLOSURE_SYSTEMS,
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

        2022 and 2024 Values:
            - (Revisionspåtegning)  / (Auditor's report on audited financial statements)
            - (Erklæring om udvidet gennemgang) / (Auditor's report on extended review)
            - (Den uafhængige revisors erklæringer (review)) / (The independent auditor's reports (Review))
            - (Andre erklæringer med sikkerhed) / (The independent auditor's reports (Other assurance Reports))
            - (Andre erklæringer uden sikkerhed) / (Auditor's reports (Other non-assurance reports))

        2025+ Values:
            - (Den uafhængige revisors erklæring) / (Independent Auditor’s Report)
            - (Den uafhængige revisors erklæring om udvidet gennemgang) / (Independent Practitioner’s Extended Review Report)
            - (Den uafhængige revisors reviewerklæring) / (Independent Practitioner’s Review Report)
            - (Andre erklæringer med sikkerhed) / (The independent auditor's reports (Other assurance Reports))
            - (Andre erklæringer uden sikkerhed) / (Auditor's reports (Other non-assurance reports))
    """
    modelXbrl = val.modelXbrl
    if val.disclosureSystem.name in [ARL_2022_PREVIEW, ARL_2024_PREVIEW, ARL_2024_MULTI_TARGET_PREVIEW]:
        validFactValues = [
            pluginData.auditedFinancialStatementsDanish,
            pluginData.auditedFinancialStatementsEnglish,
            pluginData.auditedExtendedReviewDanish,
            pluginData.auditedExtendedReviewEnglish,
            pluginData.independentAuditorsReportReviewDanish,
            pluginData.independentAuditorsReportReviewEnglish,
            pluginData.auditedAssuranceReportsDanish,
            pluginData.auditedAssuranceReportsEnglish,
            pluginData.auditedNonAssuranceReportsDanish,
            pluginData.auditedNonAssuranceReportsEnglish,
        ]
    else:
        validFactValues = [
            pluginData.independentAuditorsReportDanish,
            pluginData.independentAuditorsReportEnglish,
            pluginData.independentPractitionersExtendedReviewReportDanish,
            pluginData.independentPractitionersExtendedReviewReportEnglish,
            pluginData.independentPractitionersReviewReportDanish,
            pluginData.independentPractitionersReviewReportEnglish,
            pluginData.auditedAssuranceReportsDanish,
            pluginData.auditedAssuranceReportsEnglish,
            pluginData.auditedNonAssuranceReportsDanish,
            pluginData.auditedNonAssuranceReportsEnglish,
        ]
    facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn, set())
    for fact in facts:
        if fact.xValid >= VALID:
            if fact.xValue in validFactValues:
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


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr107(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR107: There are dates in the accounting period where no accounting system is specified
    """
    # Registered Accounting Systems
    startDatesFacts = val.modelXbrl.factsByQname.get(pluginData.startDateForUseOfDigitalStandardBookkeepingSystemQn, set())
    endDatesFacts = val.modelXbrl.factsByQname.get(pluginData.endDateForUseOfDigitalStandardBookkeepingSystemQn, set())
    bookkeepingSystemFacts = val.modelXbrl.factsByQname.get(pluginData.registrationNumberOfTheDigitalStandardBookkeepingSystemUsedQn, set())
    if len(startDatesFacts) > 0 and len(endDatesFacts) > 0 and len(bookkeepingSystemFacts) < 1:
        yield Validation.error(
            codes='DBA.FR107',
            msg=_("The date concepts of `StartDateForUseOfDigitalStandardBookkeepingSystem` and `EndDateForUseOfDigitalStandardBookkeepingSystem`"
                  "are tagged without the concept of `RegistrationNumberOfTheDigitalStandardBookkeepingSystemUsed` being tagged."),
            modelObject=startDatesFacts | endDatesFacts
        )
    # Non-Registered Accounting Systems
    startDatesFacts = val.modelXbrl.factsByQname.get(pluginData.startDateForUseOfDigitalNonregisteredBookkeepingSystemQn, set())
    endDatesFacts = val.modelXbrl.factsByQname.get(pluginData.endDateForUseOfDigitalNonregisteredBookkeepingSystemQn, set())
    bookkeepingSystemFacts = val.modelXbrl.factsByQname.get(pluginData.typeOfDigitalNonregisteredBookkeepingSystemQn, set())
    if len(startDatesFacts) > 0 and len(endDatesFacts) > 0 and len(bookkeepingSystemFacts) < 1:
        yield Validation.error(
            codes='DBA.FR107',
            msg=_("The date concepts of `StartDateForUseOfDigitalNonregisteredBookkeepingSystem` and `EndDateForUseOfDigitalNonregisteredBookkeepingSystem`"
                  "are tagged without the concept of `TypeOfDigitalNonregisteredBookkeepingSystem` being tagged."),
            modelObject=startDatesFacts | endDatesFacts
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr108(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR108: There are accounting systems whose periods overlap.
    """
    allGroupedFacts = pluginData.getBookkeepingPeriods(val.modelXbrl)
    if len(allGroupedFacts) > 0:
        for i in range(len(allGroupedFacts) - 1):
            currentPeriod = allGroupedFacts[i]
            nextPeriod = allGroupedFacts[i + 1]
            currentEndDate = currentPeriod[1].xValue
            nextStartDate = nextPeriod[0].xValue
            if currentEndDate is not None and nextStartDate is not None and cast(datetime.date, currentEndDate) > cast(datetime.date, nextStartDate):
                yield Validation.error(
                    codes='DBA.FR108',
                    msg=_("There are periods that overlap between accounting systems.\n"
                          "For registered accounting systems the periods are defined by `StartDateForUseOfDigitalStandardBookkeepingSystem` and `EndDateForUseOfDigitalStandardBookkeepingSystem`. \n"
                          "For non-registered accounting systems the periods are defined by `StartDateForUseOfDigitalNonregisteredBookkeepingSystem` and `EndDateForUseOfDigitalNonregisteredBookkeepingSystem`.\n"
                          ),
                    modelObject=currentPeriod + nextPeriod
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr109(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR109: There are one or more accounting systems whose period is outside the accounting period.

    For consolidated reports the accounting period to use is marked with AllReportingPeriodsMember.
    For reports that use floating accounting periods, the accounting period to use is marked with RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember.
    """
    def findFact(factSet: set[ModelFact], qname: QName) -> ModelFact | None:
        for fact in factSet:
          if fact is not None and fact.xValid >= VALID and fact.qname == qname:
            return fact
        return None

    accountingPeriodStartFact = None
    accountingPeriodEndFact = None
    allReportingMemberFacts = val.modelXbrl.factsByDimMemQname(pluginData.typeOfReportingPeriodDimensionQn, pluginData.allReportingPeriodsMemberQn)
    if len(allReportingMemberFacts) >1:
        accountingPeriodStartFact = findFact(allReportingMemberFacts, pluginData.reportingPeriodStartDateQn)
        if accountingPeriodStartFact is not None:
            accountingPeriodEndFact = findFact(allReportingMemberFacts, pluginData.reportingPeriodEndDateQn)
    if accountingPeriodEndFact is None:
        accountingPeriodStartFact = None
    deviatingReportingMemberFacts = val.modelXbrl.factsByDimMemQname(pluginData.typeOfReportingPeriodDimensionQn, pluginData.registeredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMemberQn)
    if len(deviatingReportingMemberFacts) >1:
        accountingPeriodStartFact = findFact(deviatingReportingMemberFacts, pluginData.reportingPeriodStartDateQn)
        accountingPeriodEndFact = findFact(deviatingReportingMemberFacts, pluginData.reportingPeriodEndDateQn)
    if accountingPeriodStartFact is None or accountingPeriodEndFact is None:
        return
    allGroupedFacts = pluginData.getBookkeepingPeriods(val.modelXbrl)
    if len(allGroupedFacts) > 0:
        if (allGroupedFacts[0][0].xValue is not None and cast(datetime.date, allGroupedFacts[0][0].xValue) < cast(datetime.date, accountingPeriodStartFact.xValue)) or (allGroupedFacts[-1][1].xValue is not None and cast(datetime.date, allGroupedFacts[-1][1].xValue) > cast(datetime.date, accountingPeriodEndFact.xValue)):
            yield Validation.error(
                codes='DBA.FR109',
                msg=_("There are accounting systems whose period is outside the accounting period."),
                modelObject=[accountingPeriodStartFact, accountingPeriodEndFact, allGroupedFacts[0][0], allGroupedFacts[-1][1]]
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr115(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR115: It is not possible to specify an end date for using an accounting system before the start date
    """
    allGroupedFacts = pluginData.getBookkeepingPeriods(val.modelXbrl)
    if len(allGroupedFacts) > 0:
        for facts in allGroupedFacts:
            if facts[0].xValue is not None and facts[1].xValue is not None and cast(datetime.date, facts[0].xValue) > cast(datetime.date, facts[1].xValue):
                yield Validation.error(
                    codes='DBA.FR115',
                    msg=_("It is not possible to specify an end date for using an accounting system before the start date.\n"
                          "Start Date: %(startDate)s,   End Date: %(endDate)s."),
                    startDate=facts[0].xValue,
                    endDate=facts[1].xValue,
                    modelObject=facts
                )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr116(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR116: It is not permitted to declare numeric fields with multiple values in the same period.
    """
    dimensionQn = pluginData.reportedValueOtherRenderingOfReportedValueDimensionQn
    otherRenderingMemberQn = pluginData.otherRenderingOfReportedValueMemberQn
    duplicateFactSets = ValidateDuplicateFacts.getDuplicateFactSetsWithType(val.modelXbrl.facts, DuplicateType.INCOMPLETE)
    for duplicateFactSet in duplicateFactSets:
        if not duplicateFactSet.areNumeric:
            continue
        reportedValueFacts = {
            fact
            for fact in duplicateFactSet.facts
            if fact.context is None or fact.context.dimMemberQname(dimensionQn) != otherRenderingMemberQn
        }
        if len(reportedValueFacts) > 1:
            yield Validation.warning(
                codes='DBA.FR116',
                msg=_("It is not permitted to declare numeric fields with multiple values in the same period."),
                modelObject=reportedValueFacts,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr117(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR117: The rendering dimension may only be used for numeric fields.
    """
    dimensionQn = pluginData.reportedValueOtherRenderingOfReportedValueDimensionQn
    otherRenderingMemberQn = pluginData.otherRenderingOfReportedValueMemberQn
    facts = val.modelXbrl.factsByDimMemQname(dimensionQn, otherRenderingMemberQn)
    invalidFacts = [fact for fact in facts if not fact.isNumeric]
    if len(invalidFacts) > 0:
        yield Validation.warning(
            codes='DBA.FR117',
            msg=_("The rendering dimension may only be used for numeric fields."),
            modelObject=invalidFacts,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=STAND_ALONE_DISCLOSURE_SYSTEMS,
)
def rule_fr118(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR118: Fields that appear in the other rendering dimension
    must also appear in the reported dimension with a different scale.
    """
    dimensionQn = pluginData.reportedValueOtherRenderingOfReportedValueDimensionQn
    otherRenderingMemberQn = pluginData.otherRenderingOfReportedValueMemberQn

    # Find "other rendering" contexts and map reported value contexts for matching later
    otherRenderingContextsMap = defaultdict(list)
    reportedValueContextsMap = defaultdict(list)
    for contextId, context in val.modelXbrl.contexts.items():
        # An "other rendering" and "reported value" context match if they are effectively duplicate contexts
        # when ignoring the "other rendering" dimension member
        key = (
            context.startDatetime,
            context.endDatetime,
            context.entityIdentifier,
            tuple(
                (dimConcept, dimMember)
                for dimConcept, dimMember in sorted(context.scenDimValues.items(), key=lambda item: item[0].localName)
                if dimConcept.qname != dimensionQn
            )
        )
        if context.dimMemberQname(dimensionQn) == otherRenderingMemberQn:
            otherRenderingContextsMap[key].append(context)
        else:
            reportedValueContextsMap[key].append(context)

    if not otherRenderingContextsMap:
        # No "other reporting" contexts, nothing to validate
        return

    factsByContextId = pluginData.factsByContextId(val.modelXbrl)

    invalidFacts: list[ModelFact] = []
    for key, otherRenderingContexts in otherRenderingContextsMap.items():
        for otherRenderingContext in otherRenderingContexts:
            if otherRenderingContext.id is None:
                continue
            # Map "other rendering" facts by (qname, unitID) for quick lookup
            # We'll remove matched facts from this map as we find them
            otherRenderingFactsMap: dict[tuple[QName, str], set[ModelFact]] = defaultdict(set)
            for otherRenderingFact in factsByContextId.get(otherRenderingContext.id, set()):
                if not otherRenderingFact.isNumeric:
                    # Validated by FR117
                    continue
                otherRenderingFactsMap[(otherRenderingFact.qname, otherRenderingFact.unitID)].add(otherRenderingFact)

            # Iterate over each "reported value" context, matched by a key that indicates that are effectively
            # duplicate contexts except for the "other rendering" dimension member
            for reportedValueContext in reportedValueContextsMap.get(key, []):
                if reportedValueContext.id is None:
                    continue
                reportedValueFacts = factsByContextId.get(reportedValueContext.id, set())
                for reportedValueFact in reportedValueFacts:
                    fact_key = (reportedValueFact.qname, reportedValueFact.unitID)
                    if fact_key not in otherRenderingFactsMap:
                        continue
                    matchingOtherRenderingFacts = {
                        _fact
                        for _fact in otherRenderingFactsMap.get(fact_key, set())
                        if _fact.scaleInt != reportedValueFact.scaleInt  # type: ignore[attr-defined]
                    }
                    otherRenderingFactsMap[fact_key] -= matchingOtherRenderingFacts

            # Any remaining "other rendering" facts have not been matched
            # with a "reported value" fact with a different scale
            for __, otherRenderingFacts in otherRenderingFactsMap.items():
                invalidFacts.extend(otherRenderingFacts)

    if invalidFacts:
        yield Validation.warning(
            codes='DBA.FR118',
            msg=_("Fields that appear in the other rendering dimension must also appear in the reported dimension with a different scale."),
            modelObject=invalidFacts,
        )
