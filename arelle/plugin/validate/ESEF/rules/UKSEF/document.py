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
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc20(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC20: UKSEF instance documents MUST use the UTF-8 character encoding.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc21(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC21: UKSEF report package "publisherCountry" metadata element MUST be "GB".
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None
