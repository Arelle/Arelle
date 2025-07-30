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
from ..DisclosureSystems import (DISCLOSURE_SYSTEM_EDINET)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[DISCLOSURE_SYSTEM_EDINET],
)
def rule_EC8033W(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    EDINET.EC8033W: The startDate of a context whose context ID starts with
    "CurrentYear" is not set to a date earlier than the endDate of a context
    whose context ID starts with "Prior1Year".
    """
    priorYearContexts = [
        context
        for contextId, context in val.modelXbrl.contexts.items()
        if contextId.startswith('Prior1Year')
           and context.endDatetime is not None
           and context.isStartEndPeriod
    ]
    latestPriorYearContext = None
    for priorYearContext in priorYearContexts:
        if latestPriorYearContext is None or \
                priorYearContext.endDatetime > latestPriorYearContext.endDatetime:
            latestPriorYearContext = priorYearContext
    if latestPriorYearContext is None:
        return
    currentYearContexts = [
        context
        for contextId, context in val.modelXbrl.contexts.items()
        if contextId.startswith('CurrentYear')
           and context.startDatetime is not None
           and context.isStartEndPeriod
    ]
    earliestCurrentYearContext = None
    for currentYearContext in currentYearContexts:
        if earliestCurrentYearContext is None or \
                currentYearContext.endDatetime > earliestCurrentYearContext.startDatetime:
            earliestCurrentYearContext = currentYearContext
    if earliestCurrentYearContext is None:
        return
    if latestPriorYearContext.endDatetime > earliestCurrentYearContext.startDatetime:
        yield Validation.warning(
            codes='EDINET.EC8033W',
            msg=_("The startDate element of the current year context (id=%(currentYearContextId)s) is "
                  "set to a date that is earlier than the endDate element of the prior year context "
                  "(id=%(priorYearContextId)s). Please check the corresponding context ID "
                  "%(currentYearContextId)s and %(priorYearContextId)s. Set the startDate element of "
                  "context ID %(currentYearContextId)s to a date that is later than or equal to the "
                  "endDate element of context ID %(priorYearContextId)s."),
            currentYearContextId=earliestCurrentYearContext.id,
            priorYearContextId=latestPriorYearContext.id,
            modelObject=priorYearContexts + currentYearContexts,
        )
