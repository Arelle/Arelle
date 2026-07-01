"""
See COPYRIGHT.md for copyright information.

UKSEF package validation rules (UKFRC9-UKFRC19).
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
def rule_ukfrc9(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC9: Package structure validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC10: Package content validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC11: Package naming convention validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc12(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC12: Package metadata validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc13(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC13: Package file type validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc14(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC14: Package encoding validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc15(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC15: Package size validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC16: Package document count validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc17(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC17: Package image format validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc18(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC18: Package CSS validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=ALL_DISCLOSURE_SYSTEMS,
)
def rule_ukfrc19(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC19: Package JavaScript validation.
    """
    if not pluginData.isUksefFiling:
        return None
    return None
