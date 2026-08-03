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
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc3(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC3: If the target attribute exists on certain key Inline XBRL elements their content
    is diverted to a target XBRL document with a name derived from the attribute value, which
    for the UK MUST be "UKFRS" (all caps).
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc4(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC4: In accordance with the ESEF Reporting Manual, Rule 2.5.3, 'All [ESEF] tagged data MUST
    be in the "default" target XBRL document'. ESEF tagged data MUST NOT carry a target attribute.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc5(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC5: In a UKSEF report, there should be two ix:references containers – one should contain the
    schemaRef for the issuer’s private extension as per ESEF requirements and MUST omit the target.
    The other must contain a UKSEF schemaRef with the "UKFRS" target attribute.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None
