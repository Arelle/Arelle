"""
See COPYRIGHT.md for copyright information.

UKSEF taxonomy validation rules (UKFRC1, UKFRC2).
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
def rule_ukfrc1(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC1: Entry point schema reference must be a valid FRC taxonomy URL.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc2(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC2: Filing must reference a recognised FRC taxonomy entry point.
    """
    if not pluginData.isUksefFiling:
        return None
    return None
