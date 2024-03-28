"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

import datetime
from typing import Any, Iterable

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from . import getValidFactPairs
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr4(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    DBA.FR4: The end date of the accounting period (gsd:ReportingPeriodEndDate with
    default TypeOfReportingPeriodDimension) must not be before the start date of the
    accounting period (gsd:ReportingPeriodStartDate with default TypeOfReportingPeriodDimension)

    Implementation: Find all combinations of gsd:ReportingPeriodStartDate and
    gsd:ReportingPeriodEndDate facts and trigger error whenever end date is before
    start date
    """
    pairs = getValidFactPairs(
        val.modelXbrl,
        pluginData.reportingPeriodStartDateQn,
        pluginData.reportingPeriodEndDateQn
    )
    for startDateFact, endDateFact in pairs:
        if not isinstance(startDateFact.xValue, datetime.datetime) or \
                not isinstance(endDateFact.xValue, datetime.datetime):
            continue
        if startDateFact.xValue <= endDateFact.xValue:
            continue
        yield Validation.error(
            codes="DBA.FR4",
            msg=_("Error code FR4: Accounting period end date='%(endDate)s' "
                  "must not be before Accounting period start date='%(startDate)s'"),
            modelObject=[startDateFact, endDateFact],
            endDate=endDateFact.xValue,
            startDate=startDateFact.xValue,
        )
