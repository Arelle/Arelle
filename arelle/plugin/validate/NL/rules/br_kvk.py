"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from . import (
    FINANCIAL_REPORTING_PERIOD_CURRENT_END_DATE_QN,
    FINANCIAL_REPORTING_PERIOD_CURRENT_START_DATE_QN,
    FINANCIAL_REPORTING_PERIOD_PREVIOUS_END_DATE_QN,
    FINANCIAL_REPORTING_PERIOD_PREVIOUS_START_DATE_QN
)
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


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

    def getDateValue(qname):
        facts = modelXbrl.factsByQname.get(qname)
        assert facts and len(facts) == 1, _('Exactly one fact must exist for reporting period concept: {0}').format(qname)
        value = next(iter(facts)).value
        return datetime.strptime(value, "%Y-%m-%d").date()

    currentDuration = (
        getDateValue(FINANCIAL_REPORTING_PERIOD_CURRENT_START_DATE_QN),
        getDateValue(FINANCIAL_REPORTING_PERIOD_CURRENT_END_DATE_QN)
    )
    previousDuration = (
        getDateValue(FINANCIAL_REPORTING_PERIOD_PREVIOUS_START_DATE_QN),
        getDateValue(FINANCIAL_REPORTING_PERIOD_PREVIOUS_END_DATE_QN)
    )
    validDurations = (currentDuration, previousDuration)
    validInstants = (
        currentDuration[1],
        (currentDuration[0] + timedelta(days=-1)),
        (previousDuration[0] + timedelta(days=-1))
    )

    for contextId, context in modelXbrl.contexts.items():
        if context.isInstantPeriod:
            # instantDatetime getter adds a day, we need to subtract for comparison
            instantDate = (context.instantDatetime + timedelta(days=-1)).date()
            if instantDate in validInstants:
                continue
        if context.isStartEndPeriod:
            contextDates = (
                context.startDatetime.date(),
                # endDatetime getter adds a day, we need to subtract for comparison
                (context.endDatetime + timedelta(days=-1)).date()
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
