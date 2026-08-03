"""
See COPYRIGHT.md for copyright information.

UKSEF context validation rules (UKFRC8).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc8(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC8: xbrli:segment elements MUST be used in the contexts of UKFRS target FRC-tagged data.
    xbrli:scenario elements MUST be used in the contexts of default target ESEF-tagged data.
    """
    if val.authority != AUTHORITY_UKFRC:
        return
    modelXbrl = val.modelXbrl
    contextIssues = pluginData.getContextIssues(modelXbrl)
    if pluginData.isUkfrsTarget(modelXbrl):
        if contextIssues.contextsWithScenarios:
            yield Validation.error(
                "ESEF.UKFRC8.scenarioUsed",
                _("xbrli:segment elements MUST be used in the contexts of UKFRS target FRC-tagged data. : %(contextIds)s"),
                modelObject=contextIssues.contextsWithScenarios,
                contextIds=", ".join(c.id for c in contextIssues.contextsWithScenarios if c.id is not None)
            )
    else:
        if contextIssues.contextsWithSegments:
            yield Validation.error(
                "ESEF.UKFRC8.segmentUsed",
                _("xbrli:scenario elements MUST be used in the contexts of default target ESEF-tagged data: %(contextIds)s"),
                modelObject=contextIssues.contextsWithSegments,
                contextIds=", ".join(c.id for c in contextIssues.contextsWithSegments if c.id is not None)
            )
