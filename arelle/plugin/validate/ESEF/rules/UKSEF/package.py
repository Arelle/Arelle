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
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc9(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC9: UKSEF report package MUST be submitted in a zipped report package (*.zip or *.xbri extensions only)
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc10(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC10: The report package MUST include only one report in the “reports” directory.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc11(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC11: Subdirectories MUST NOT be used in the “reports” directory and
    MUST NOT contain more than one iXBRL document.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc12(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC12: The report MUST be XHTML tagged using the iXBRL format with a .html
    or .xhtml file extension only.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc13(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC13: Script-based iXBRL viewers MUST NOT be included either as part of
    iXBRL documents or as a separate resource.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc14(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC14: For tagged files, images can be provided either in the XHTML document
    as a base64 encoded string or be referenced as separate files in the package.
    The use of these two methods MUST NOT be combined.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc15(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC15: If images are contained in separate files in the package, they MUST be in
    PNG, GIF, SVG or JPG/JPEG format. All the external referenced images MUST be placed
    in the same location within the zip package.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc16(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC16: CSS MUST be embedded in the XHTML document.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc17(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC17: For a report package, issuers are required to adopt a naming convention
    which matches {base}-{date}.zip or {base}-{date}.xbri, whereby:
    *	The {base} component of the filename shall indicate the LEI of the issuer
    *	The {date} component of the filename should indicate the accounting reference date.
        The {date} component should follow the YYYY-MM-DD format.
    E.g. 213800YWQOYL4VQODV50-2022-12-31.zip.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc18(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC18: For a tagged xHTML file within a report package, issuers are required to
    adopt a naming convention which matches {base}-{date}.html or .xhtml whereby:
    *	The {base} component of the filename shall indicate the LEI of the issuer
    *	The {date} component of the filename should indicate the accounting reference date.
        The {date} component should follow the YYYY-MM-DD format.
    E.g. 213800YWQOYL4VQODV50-2022-12-31.html
    The filename MAY also end with "-T01"
    Note: This differs from the ESEF requirement which specifies a language component as well
    (hence the ESEF package name errors in all cases)
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc19(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    UKFRC19: Any other file present in a report package MUST NOT include spaces in the filename.
    """
    if val.authority != AUTHORITY_UKFRC:
        return None
    return None
