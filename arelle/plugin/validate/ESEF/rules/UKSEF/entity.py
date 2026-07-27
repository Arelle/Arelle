"""
See COPYRIGHT.md for copyright information.

UKSEF entity validation rules (UKFRC6, UKFRC7).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle import XbrlConst
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from . import ENTITY_IDENTIFIER_SCHEME_CRN
from ...Const import AUTHORITY_UKFRC
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc6(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC6: The "default" target document must use the LEI entity scheme (https://www.iso.org/standard/78829.html).
    The same LEI MUST be used throughout the document.
    """
    if val.authority != AUTHORITY_UKFRC:
        return
    modelXbrl = val.modelXbrl
    if pluginData.isUkfrsTarget(modelXbrl):
        return
    invalidSchemeRefs = []
    contextsByEntityIdentifier = pluginData.getContextsByEntityIdentifier(modelXbrl)
    for (scheme, __), contexts in contextsByEntityIdentifier.items():
        if scheme != XbrlConst.iso17442:
            invalidSchemeRefs.extend(contexts)
    if invalidSchemeRefs:
        yield Validation.error(
            "ESEF.UKFRC6.invalidIdentifier",
            _("The default target document must use the LEI entity scheme (%(requiredScheme)s)."),
            requiredScheme=XbrlConst.iso17442,
            modelObject=invalidSchemeRefs,
        )
    if len(contextsByEntityIdentifier) > 1:
        yield Validation.error(
            "ESEF.UKFRC6.multipleIdentifiers",
            _("The same LEI MUST be used throughout the default target (%(identifiers)s)."),
            identifiers=", ".join(
                f"{scheme} - {identifier}"
                for scheme, identifier in contextsByEntityIdentifier
            ),
        )

@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc7(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC7: The "UKFRS" target document must use the CRN entity scheme (http://www.companieshouse.gov.uk/).
    The same CRN MUST be used throughout the document.
    """
    if val.authority != AUTHORITY_UKFRC:
        return
    modelXbrl = val.modelXbrl
    if not pluginData.isUkfrsTarget(modelXbrl):
        return
    invalidSchemeRefs = []
    contextsByEntityIdentifier = pluginData.getContextsByEntityIdentifier(modelXbrl)
    for (scheme, __), contexts in contextsByEntityIdentifier.items():
        if scheme != ENTITY_IDENTIFIER_SCHEME_CRN:
            invalidSchemeRefs.extend(contexts)
    if invalidSchemeRefs:
        yield Validation.error(
            "ESEF.UKFRC7.invalidIdentifier",
            _("The UKFRS target document must use the CRN entity scheme (%(requiredScheme)s)."),
            requiredScheme=ENTITY_IDENTIFIER_SCHEME_CRN,
            modelObject=invalidSchemeRefs,
        )
    if len(contextsByEntityIdentifier) > 1:
        yield Validation.error(
            "ESEF.UKFRC7.multipleIdentifiers",
            _("The same CRN MUST be used throughout the UKFRS target (%(identifiers)s)."),
            identifiers=",".join(
                f"{scheme} - {identifier}"
                for scheme, identifier in contextsByEntityIdentifier
            ),
        )
