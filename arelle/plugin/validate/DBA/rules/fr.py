"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from . import errorOnDateFactComparison
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
    """
    return errorOnDateFactComparison(
        val.modelXbrl,
        fact1Qn=pluginData.reportingPeriodStartDateQn,
        fact2Qn=pluginData.reportingPeriodEndDateQn,
        dimensionQn=pluginData.typeOfReportingPeriodDimensionQn,
        code='DBA.FR4',
        message=_("Error code FR4: Accounting period end date='%(fact2)s' "
                  "must not be before Accounting period start date='%(fact1)s'"),
        assertion=lambda startDate, endDate: startDate <= endDate,
    )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_fr5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    DBA.FR5: General meeting date (gsd:DateOfGeneralMeeting) must not be before the
    end date of the accounting period (gsd:ReportingPeriodEndDate with default
    TypeOfReportingPeriodDimension)
    """
    return errorOnDateFactComparison(
        val.modelXbrl,
        fact1Qn=pluginData.reportingPeriodEndDateQn,
        fact2Qn=pluginData.dateOfGeneralMeetingQn,
        dimensionQn=pluginData.typeOfReportingPeriodDimensionQn,
        code='DBA.FR5',
        message=_("Error code FR5: General meeting date='%(fact2)s' "
                  "must be after Accounting period end date='%(fact1)s'"),
        assertion=lambda endDate, meetingDate: endDate < meetingDate,
    )
