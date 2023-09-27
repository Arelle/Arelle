"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, TYPE_CHECKING

from arelle import XmlUtil
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from . import (
    DOCUMENTATION_ADOPTION_DATE_QN,
    DOCUMENTATION_ADOPTION_STATUS_QN,
    DOCUMENT_RESUBMISSION_UNSURMOUNTABLE_INACCURACIES_QN,
    FINANCIAL_REPORTING_PERIOD_CURRENT_END_DATE_QN,
    FINANCIAL_REPORTING_PERIOD_CURRENT_START_DATE_QN,
    FINANCIAL_REPORTING_PERIOD_PREVIOUS_END_DATE_QN,
    FINANCIAL_REPORTING_PERIOD_PREVIOUS_START_DATE_QN,
)
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

if TYPE_CHECKING:
    from arelle.ModelXbrl import ModelXbrl
    from arelle.ModelValue import QName

_: TypeGetText


def _getReportingPeriodDateValue(modelXbrl: ModelXbrl, qname: QName) -> date | None:
    facts = modelXbrl.factsByQname.get(qname)
    if facts and len(facts) == 1:
        return XmlUtil.datetimeValue(next(iter(facts))).date()
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_2_04(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-2.04: The period in the context MUST correspond to the period of the current or
    previous financial reporting period, or one day before the start of the comparative financial
    where the context must be instant.

    Example:
        Reporting Period Start Date: 2018-01-01
        Reporting Period End Date: 2018-12-31

    | Context | Instant    | Start Date | End Date   | Note                                                    |
    | ------- | ---------- | ---------- | ---------- | ------------------------------------------------------- |
    | 1       | 2018-12-31 |            |            | End value as context for the current reporting period   |
    | 2       |            | 2018-12-31 | 2018-12-31 | Current reporting period                                |
    | 3       | 2017-12-31 |            |            | End value as context for previous reporting period      |
    | 4       |            | 2017-12-31 | 2017-12-31 | Previous reporting period                               |
    | 5       | 2016-12-31 |            |            | Starting value as context for previous reporting period |

    """
    modelXbrl = val.modelXbrl

    currentDuration = (
        _getReportingPeriodDateValue(modelXbrl, FINANCIAL_REPORTING_PERIOD_CURRENT_START_DATE_QN),
        _getReportingPeriodDateValue(modelXbrl, FINANCIAL_REPORTING_PERIOD_CURRENT_END_DATE_QN)
    )
    if None in currentDuration:
        return
    previousDuration = (
        _getReportingPeriodDateValue(modelXbrl, FINANCIAL_REPORTING_PERIOD_PREVIOUS_START_DATE_QN),
        _getReportingPeriodDateValue(modelXbrl, FINANCIAL_REPORTING_PERIOD_PREVIOUS_END_DATE_QN)
    )
    if None in previousDuration:
        return
    validDurations = (currentDuration, previousDuration)
    validInstants = (
        currentDuration[1],
        (currentDuration[0] - timedelta(1)),
        (previousDuration[0] - timedelta(1))
    )

    for contextId, context in modelXbrl.contexts.items():
        if context.isInstantPeriod:
            if context.instantDate in validInstants:
                continue
        if context.isStartEndPeriod:
            contextDates = (
                context.startDatetime.date(),
                context.endDate
            )
            if contextDates in validDurations:
                continue
        yield Validation.error(
            codes='BR-KVK-2.04',
            msg=_('The period in the context MUST correspond to the period of the current (%(currentDuration)s) or '
                  'previous (%(previousDuration)s) financial reporting period, or one day before the start of the comparative '
                  'financial year (%(instants)s) where the context must be instant. Context: %(contextId)s'),
            modelObject=context,
            contextId=contextId,
            currentDuration=[str(d) for d in currentDuration],
            previousDuration=[str(d) for d in previousDuration],
            instants=[str(d) for d in validInstants],
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_3_01(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-3.01: A measure element with a namespace prefix that refers to the
    "http://www.xbrl.org/2003/iso4217" namespace MUST appear exactly once in the instance document.
    """
    modelXbrl = val.modelXbrl
    currencyUnitIds = set()
    currencyMeasures = []
    for unitId, unit in modelXbrl.units.items():
        for measures in unit.measures:
            for measure in measures:
                if measure.namespaceURI == 'http://www.xbrl.org/2003/iso4217':
                    currencyUnitIds.add(unitId)
                    currencyMeasures.append(measure)
    if len(currencyMeasures) != 1:
        yield Validation.error(
            codes='BR-KVK-3.01',
            msg=_('A measure element with a namespace prefix that refers to the "http://www.xbrl.org/2003/iso4217" '
                  'namespace MUST appear exactly once in the instance document. Units: %(unitIds)s, Measures: %(measures)s'),
            unitIds=list(currencyUnitIds),
            measures=[str(m) for m in currencyMeasures]
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_4_07(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-4.07: The jenv-bw2-i:FinancialReportingPeriodCurrentEndDate MUST be before the date of filing.
    """
    modelXbrl = val.modelXbrl
    currentPeriodEndDate = _getReportingPeriodDateValue(modelXbrl, FINANCIAL_REPORTING_PERIOD_CURRENT_END_DATE_QN)
    if currentPeriodEndDate is None:
        return
    filingDate = date.today()
    if currentPeriodEndDate >= filingDate:
        yield Validation.error(
            codes='BR-KVK-4.07',
            msg=_('The jenv-bw2-i:FinancialReportingPeriodCurrentEndDate (%(currentPeriodEndDate)s) '
                  'MUST be before the date of filing (%(filingDate)s).'),
            currentPeriodEndDate=currentPeriodEndDate,
            filingDate=filingDate,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_4_10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-4.10: The jenv-bw2-i:DocumentAdoptionDate MUST NOT be after the date of filing.
    """
    modelXbrl = val.modelXbrl
    documentAdoptionDate = _getReportingPeriodDateValue(modelXbrl, DOCUMENTATION_ADOPTION_DATE_QN)
    if documentAdoptionDate is None:
        return
    filingDate = date.today()
    if documentAdoptionDate > filingDate:
        yield Validation.error(
            codes='BR-KVK-4.10',
            msg=_('The jenv-bw2-i:DocumentAdoptionDate (%(documentAdoptionDate)s) '
                  'MUST NOT be after the date of filing (%(filingDate)s).'),
            documentAdoptionDate=documentAdoptionDate,
            filingDate=filingDate,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_4_12(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-4.12: For a corrected annual report, an annual report to be corrected
    MUST be filed with the Trade Register.
    If kvk-i:DocumentResubmissionDueToUnsurmountableInaccuracies is "Ja" (Yes),
    then jenv-bw2-i:DocumentAdoptionStatus must be "Ja" (Yes).
    """
    modelXbrl = val.modelXbrl
    resubmissionConceptQname = DOCUMENT_RESUBMISSION_UNSURMOUNTABLE_INACCURACIES_QN
    if not any(f.value == 'Ja' for f in modelXbrl.factsByQname.get(resubmissionConceptQname, [])):
        return
    documentAdoptionStatusQname = DOCUMENTATION_ADOPTION_STATUS_QN
    if not any(f.value == 'Ja' for f in modelXbrl.factsByQname.get(documentAdoptionStatusQname, [])):
        yield Validation.error(
            codes='BR-KVK-4.12',
            msg=_('For a corrected annual report, an annual report to be corrected '
                  'MUST be filed with the Trade Register. '
                  'If %(resubmissionConceptQname)s is "Ja" (Yes), '
                  'then %(documentAdoptionStatusQname)s must be "Ja" (Yes).'),
            resubmissionConceptQname=resubmissionConceptQname,
            documentAdoptionStatusQname=documentAdoptionStatusQname,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_4_16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-4.16: A corrected financial statement MUST be established.
    If kvk-i:DocumentResubmissionDueToUnsurmountableInaccuracies is "Ja" (Yes),
    the following facts must be filled for a corrected financial statement:
    jenv-bw2-i:DocumentAdoptionStatus
    jenv-bw2-i:DocumentAdoptionDate
    """
    modelXbrl = val.modelXbrl
    resubmissionConceptQname = DOCUMENT_RESUBMISSION_UNSURMOUNTABLE_INACCURACIES_QN
    if not any(f.value == 'Ja' for f in modelXbrl.factsByQname.get(resubmissionConceptQname, [])):
        return
    requiredConceptQnames = (
        DOCUMENTATION_ADOPTION_DATE_QN,
        DOCUMENTATION_ADOPTION_STATUS_QN
    )
    for conceptQname in requiredConceptQnames:
        if not any(f.value for f in modelXbrl.factsByQname.get(conceptQname, [])):
            yield Validation.error(
                codes='BR-KVK-4.16',
                msg=_('A corrected financial statement MUST be established. '
                      'If %(resubmissionConceptQname)s is "Ja" (Yes), '
                      '%(conceptQname)s must be filled for a corrected financial statement.'),
                resubmissionConceptQname=resubmissionConceptQname,
                conceptQname=conceptQname,
            )
