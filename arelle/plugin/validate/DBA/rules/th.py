"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ModelObjectFactory import SCHEMA, ModelDocument

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_th06 (
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TH06: CVR (gsd:IdentificationNumberCvrOfReportingEntity) context period cannot be forever.
    """
    facts = val.modelXbrl.factsByQname.get(pluginData.identificationNumberCvrOfReportingEntityQn, set())
    for fact in facts:
        if fact is not None and fact.context is not None:
            if fact.context.isForeverPeriod:
                yield Validation.error(
                    'DBA.TH06',
                    _('The CVR (gsd:IdentificationNumberCvrOfReportingEntity) context period cannot be forever.'),
                    modelObject=fact,
                )
