"""
See COPYRIGHT.md for copyright information.

UKSEF document validation rules (UKFRC20, UKFRC21).
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
def rule_ukfrc20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC20: Document structure validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc21(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC21: Document content type validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None
