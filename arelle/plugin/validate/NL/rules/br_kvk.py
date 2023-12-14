"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import date, timedelta
from dateutil import relativedelta
from typing import Any, cast, Iterable, TYPE_CHECKING

from regex import regex

from arelle import XmlUtil, XbrlConst
from arelle.ModelObject import ModelObject
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XmlValidate import INVALID
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
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
        datetimeValue = XmlUtil.datetimeValue(next(iter(facts)))
        if datetimeValue:
            return datetimeValue.date()
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
        _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodCurrentStartDateQn),
        _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodCurrentEndDateQn)
    )
    if None in currentDuration:
        return
    previousDuration = (
        _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodPreviousStartDateQn),
        _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodPreviousEndDateQn)
    )
    if None in previousDuration:
        return
    validDurations = (currentDuration, previousDuration)
    validInstants = (
        currentDuration[1],
        (cast(date, currentDuration[0]) - timedelta(1)),
        (cast(date, previousDuration[0]) - timedelta(1))
    )

    for contextId, context in modelXbrl.contexts.items():
        if context.isInstantPeriod:
            if context.instantDate in validInstants:
                continue
        if context.isStartEndPeriod:
            contextDates = (
                context.startDatetime.date() if context.startDatetime else None,
                context.endDate
            )
            if contextDates in validDurations:
                continue
        yield Validation.error(
            codes='NL.BR-KVK-2.04',
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
    units = set()
    for unitId, unit in modelXbrl.units.items():
        for measures in unit.measures:
            for measure in measures:
                if measure.namespaceURI == 'http://www.xbrl.org/2003/iso4217':
                    currencyUnitIds.add(unitId)
                    currencyMeasures.append(measure)
                    units.add(unit)
    if len(currencyMeasures) != 1:
        yield Validation.error(
            codes='NL.BR-KVK-3.01',
            msg=_('A measure element with a namespace prefix that refers to the "http://www.xbrl.org/2003/iso4217" '
                  'namespace MUST appear exactly once in the instance document. Units: %(unitIds)s, Measures: %(measures)s'),
            modelObject=units,
            unitIds=sorted(currencyUnitIds),
            measures=sorted([str(m) for m in currencyMeasures])
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
    currentPeriodEndDate = _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodCurrentEndDateQn)
    if currentPeriodEndDate is None:
        return
    filingDate = date.today()
    if currentPeriodEndDate >= filingDate:
        yield Validation.error(
            codes='NL.BR-KVK-4.07',
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
    documentAdoptionDate = _getReportingPeriodDateValue(modelXbrl, pluginData.documentAdoptionDateQn)
    if documentAdoptionDate is None:
        return
    filingDate = date.today()
    if documentAdoptionDate > filingDate:
        yield Validation.error(
            codes='NL.BR-KVK-4.10',
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
    resubmissionConceptQname = pluginData.documentResubmissionUnsurmountableInaccuraciesQn
    if not any(f.value == 'Ja' for f in modelXbrl.factsByQname.get(resubmissionConceptQname, [])):
        return
    documentAdoptionStatusQname = pluginData.documentAdoptionStatusQn
    if not any(f.value == 'Ja' for f in modelXbrl.factsByQname.get(documentAdoptionStatusQname, [])):
        yield Validation.error(
            codes='NL.BR-KVK-4.12',
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
    resubmissionConceptQname = pluginData.documentResubmissionUnsurmountableInaccuraciesQn
    if not any(f.value == 'Ja' for f in modelXbrl.factsByQname.get(resubmissionConceptQname, [])):
        return
    requiredConceptQnames = (
        pluginData.documentAdoptionDateQn,
        pluginData.documentAdoptionStatusQn
    )
    for conceptQname in requiredConceptQnames:
        if not any(f.value for f in modelXbrl.factsByQname.get(conceptQname, [])):
            yield Validation.error(
                codes='NL.BR-KVK-4.16',
                msg=_('A corrected financial statement MUST be established. '
                      'If %(resubmissionConceptQname)s is "Ja" (Yes), '
                      '%(conceptQname)s must be filled for a corrected financial statement.'),
                resubmissionConceptQname=resubmissionConceptQname,
                conceptQname=conceptQname,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_4_17(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-4.17: The current and previous financial reporting period MUST be less than 2 years.
    """
    modelXbrl = val.modelXbrl
    current_period_end = _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodCurrentEndDateQn)
    previous_period_start = _getReportingPeriodDateValue(modelXbrl, pluginData.financialReportingPeriodPreviousStartDateQn)
    if current_period_end is not None and previous_period_start is not None:
        delta = relativedelta.relativedelta(current_period_end, previous_period_start)
        if (delta.years == 2 and (delta.months > 0 or delta.days > 0)) or delta.years > 2:
            yield Validation.error(
                codes='NL.BR-KVK-4.17',
                msg=_('The current and previous financial reporting period MUST be less than 2 years. '
                      'Previous Period Start: %(start)s  Current Period End: %(end)s '),
                start=previous_period_start,
                end=current_period_end
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_br_kvk_4_20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    BR-KVK-4.20: Each date in an XBRL instance MUST be a valid date. The date is in format YYYY-MM-DD.
    """
    modelXbrl = val.modelXbrl
    pattern = regex.compile(r"\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\s*$")
    # Check period date values
    for contextId, context in modelXbrl.contexts.items():
        for contextChild in context:
            if not isinstance(contextChild, ModelObject):
                continue
            if contextChild.elementQname != XbrlConst.qnXbrliPeriod:
                continue
            for periodChild in contextChild:
                if not isinstance(periodChild, ModelObject):
                    continue
                xValid = getattr(periodChild, 'xValid', None)
                sValue = getattr(periodChild, 'sValue', None)
                if (xValid == INVALID) or \
                        (sValue is not None and pattern.match(str(sValue))) is None:
                    yield Validation.error(
                        codes='NL.BR-KVK-4.20',
                        msg=_('Each date in an XBRL instance MUST be a valid date. '
                              'Date parsing for %(periodElement)s in context "%(contextId)s" with value "%(periodValue)s" '
                              'failed with message: "%(valueError)s" '),
                        modelObject=periodChild,
                        contextId=contextId,
                        periodElement=periodChild.qname.localName,
                        periodValue=periodChild.sValue,
                        valueError=getattr(periodChild, 'xValueError', None) or 'does not match YYYY-MM-DD',
                    )
    # Check date fact values
    for fact in modelXbrl.factsByDatatype(notStrict=True, typeQname=XbrlConst.qnXbrliDateItemType) or []:
        if (fact.xValid == INVALID) or \
                pattern.match(str(fact.sValue)) is None:
            yield Validation.error(
                codes='NL.BR-KVK-4.20',
                msg=_('Each date in an XBRL instance MUST be a valid date. '
                      'Date parsing for fact %(factQname)s with value "%(factValue)s" failed with message: "%(valueError)s" '),
                modelObject=fact,
                factQname=fact.qname,
                factValue=fact.sValue,
                valueError=fact.xValueError or 'does not match YYYY-MM-DD',
            )
