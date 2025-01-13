"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
import decimal
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
from ..ValidationPluginExtension import DANISH_CURRENCY_ID, ROUNDING_MARGIN, PERSONNEL_EXPENSE_THRESHOLD

_: TypeGetText

@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tm33(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TM33: ReportingPeriodEndDate with the dimension of
    TypeOfReportingPeriodDimension:RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember
    must only be tagged once.
    """
    modelXbrl = val.modelXbrl
    valid_facts = []
    end_date_facts = modelXbrl.factsByQname.get(pluginData.reportingPeriodEndDateQn)
    if end_date_facts is not None:
        for fact in end_date_facts:
            member = fact.context.qnameDims.get(pluginData.typeOfReportingPeriodDimensionQn)
            if member is not None and member.memberQname == pluginData.registeredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMemberQn:
                valid_facts.append(fact)
        if len(valid_facts) > 1:
            yield Validation.error(
                'DBA.TM33',
                _('ReportingPeriodEndDate with the dimension of TypeOfReportingPeriodDimension:RegisteredReportingPeriodDeviatingFromReportedReportingPeriodDueArbitraryDatesMember '
                  'must only be tagged once. {} facts were found.').format(len(valid_facts)),
                modelObject=valid_facts
            )
