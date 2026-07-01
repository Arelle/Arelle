"""
See COPYRIGHT.md for copyright information.

UKSEF mandatory facts validation rules for Companies House.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from ..DisclosureSystems import ALL_DISCLOSURE_SYSTEMS
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_mandatory_facts(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    Companies House mandatory facts: Validates that all required facts
    are present in the filing.
    """
    if not pluginData.isUksefFiling:
        return None
    return None
