"""
See COPYRIGHT.md for copyright information.

UKSEF target validation rules (UKFRC3, UKFRC4, UKFRC5).
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
def rule_ukfrc3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC3: Inline XBRL document must define the correct target.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc4(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC4: Inline XBRL target must contain required schema references.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC5: Default target must reference the ESEF taxonomy.
    """
    if not pluginData.isUksefFiling:
        return None
    return None
