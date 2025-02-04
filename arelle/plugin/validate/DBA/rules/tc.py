"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.ValidateXbrl import ValidateXbrl
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.XmlValidateConst import VALID
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_tc02(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    DBA.TC02: CPR numbers must not be used as values for typed dimensions
    """
    modelXbrl = val.modelXbrl
    possible_cpr_values = set()
    for fact in modelXbrl.facts:
        for dim_value in fact.context.scenDimValues.values():
            if (dim_value.isTyped and
                    dim_value.typedMember.xValid >= VALID and
                    pluginData.cpr_regex.match(dim_value.typedMember.xValue)):
                possible_cpr_values.add(dim_value)
    if possible_cpr_values:
        yield Validation.warning(
            'DBA.TC02',
            _('The value of a typed dimension looks like a CPR number. Please check the number and verify that it is not '
            'a CPR number as CPR numbers must not be used in typed dimension values.'),
            modelObject=possible_cpr_values
        )
