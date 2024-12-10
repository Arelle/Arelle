"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import itertools
from collections.abc import Iterable
from typing import Any, cast

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from . import errorOnDateFactComparison, errorOnRequiredFact, getFactsWithDimension, getFactsGroupedByContextId, errorOnRequiredPositiveFact
from ..PluginValidationDataExtension import PluginValidationDataExtension


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
    meetingFacts = val.modelXbrl.factsByQname.get(pluginData.dateOfGeneralMeetingQn)
    if meetingFacts:
        chairmanFacts = val.modelXbrl.factsByQname.get(pluginData.nameAndSurnameOfChairmanOfGeneralMeetingQn)
        if not chairmanFacts:
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
    equityFacts = val.modelXbrl.factsByQname.get(pluginData.equityQn)
    nonZeroEquityFacts = []
    if equityFacts:
        for fact in equityFacts:
            if fact.xValid >= VALID:
                if fact.xValue != 0:
                    nonZeroEquityFacts.append(fact)
    if nonZeroEquityFacts:
        otherRequiredFactsQnames = [
            pluginData.assetsQn, pluginData.noncurrentAssetsQn, pluginData.longtermLiabilitiesOtherThanProvisionsQn,
            pluginData.shorttermLiabilitiesOtherThanProvisionsQn, pluginData.liabilitiesOtherThanProvisionsQn, pluginData.liabilitiesAndEquityQn
        ]
        hasEquityRequiredFacts = any(val.modelXbrl.factsByQname.get(factQname) for factQname in otherRequiredFactsQnames)
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
        if cast(float, profitLossFact.xValue) <= pluginData.positiveProfitThreshold:
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
        facts = val.modelXbrl.factsByQname.get(factQname)
        if facts:
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
def rule_fr53(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.FR53: Information is missing on the audit company's CVR no. and the audit firm's name.

    The audit firm's CVR number and name of audit firm must be provided when (fsa:TypeOfAuditorAssistance) is
    tagged with one of the following values:
    - (Revisionspåtegning)  / (Auditor's report on audited financial statements)
    - (Erklæring om udvidet gennemgang) / (Auditor's report on extended review)
    - (Den uafhængige revisors erklæringer (review)) / (The independent auditor's reports (Review))
    - (Andre erklæringer med sikkerhed) / (The independent auditor's reports (Other assurance Reports))
    """
    modelXbrl = val.modelXbrl
    facts = modelXbrl.factsByQname.get(pluginData.typeOfAuditorAssistanceQn)
    if facts is not None:
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
                    cvr_facts = modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfAuditFirmQn)
                    auditor_name_facts = modelXbrl.factsByQname.get(pluginData.nameOfAuditFirmQn)
                    if cvr_facts is None:
                        missing_concepts.append(pluginData.identificationNumberCvrOfAuditFirmQn.localName)
                    if auditor_name_facts is None:
                        missing_concepts.append(pluginData.identificationNumberCvrOfAuditFirmQn.localName)
                    if len(missing_concepts) > 0:
                        yield Validation.warning(
                            codes='DBA.FR53',
                            msg = _("The following concepts must be tagged: {} when {} is tagged with the value of {}").format(
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
            profitLossValue = cast(float, fact.xValue)
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
