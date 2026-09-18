"""
See COPYRIGHT.md for copyright information.

UKSEF target validation rules (UKFRC3, UKFRC4, UKFRC5).
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from arelle.ModelObject import ModelObject
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from arelle.ValidateXbrl import ValidateXbrl
from arelle.XbrlConst import ixbrl, ixbrl11
from ...Const import AUTHORITY_UKFRC, TARGET_UKFRS
from ...PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText

# Inline XBRL elements on which the "target" attribute may legitimately appear.
_TARGET_ALLOWED_LOCAL_NAMES = ("nonFraction", "nonNumeric", "footnote", "references")
# Inline XBRL elements on which the "target" attribute MUST NOT appear.
_TARGET_DISALLOWED_LOCAL_NAMES = ("resources", "continuation", "exclude")


def _ixTagsForNamespace(ns: str, local_names: Iterable[str]) -> tuple[str, ...]:
    """
    Build the fully qualified XML tag names for a given namespace and set of local names.

    This helper converts unqualified Inline XBRL element names such as
    "nonFraction" or "references" into Clark-notation tags of the form
    "{namespaceURI}localName". These names are then compared directly against
    XML element tags when validating Inline XBRL content.

    Args:
        ns: The XML namespace URI to qualify the tag names with.
        local_names: An iterable of local element names to convert.

    Returns:
        A tuple of fully qualified tag names in the same order as the input
        local names.
    """
    return tuple(f"{{{ns}}}{ln}" for ln in local_names)


@validation(
    # using FINALLY hook to ensure that the ixdsReferences are fully populated before checking for the UKFRS target
    hook=ValidationHook.FINALLY,
)
def rule_incorrectTarget(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Validate all UKSEF incorrect-target conditions in one place.

    A UKSEF report must contain an ix:references element with the exact target value "UKFRS".
    A case-insensitive match is reported under UKFRC3, while a missing or otherwise invalid
    target is reported under UKFRC1.
    """
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isEsefTarget(val.modelXbrl)
            or not (ixdsReferences := getattr(val, "ixdsReferences", None))
            or ixdsReferences.get(TARGET_UKFRS, [])):
        return

    caseInsensitiveTargets = [
        (target, referencesElts)
        for target, referencesElts in ixdsReferences.items()
        if isinstance(target, str) and target.upper() == TARGET_UKFRS
    ]

    if caseInsensitiveTargets:
        for target, referencesElts in caseInsensitiveTargets:
            yield Validation.error(
                codes="ESEF.UKFRC3.incorrectTarget",
                msg=_(
                    'The target attribute on Inline XBRL elements in a UKSEF report MUST be '
                    '"UKFRS" (case-sensitive). Found invalid target value: "%(target)s".'
                ),
                modelObject=referencesElts,
                target=target,
            )
    else:
        yield Validation.error(
            codes="ESEF.UKFRC1.incorrectTarget",
            msg=_(
                'UKSEF reports MUST have a "UKFRS" targeted ix:references element. '
                "No matching ix:references element was found in the report."
            ),
        )


@validation(
    # using FINALLY hook to ensure that the ixdsReferences are fully populated before checking entry points
    hook=ValidationHook.FINALLY,
)
def rule_multipleEntryPoints(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    Validate all UKSEF multiple-entry-point conditions in one place.

    UKFRC1 limits the matching UKSEF schemaRefs in a single UKFRS target to one.
    UKFRC5 limits the UKFRS-targeted ix:references elements to one.
    """
    if (val.authority != AUTHORITY_UKFRC
            or not pluginData.isUkfrsTarget(val.modelXbrl)
            or not (ixdsReferences := getattr(val, "ixdsReferences", None))):
        return

    foundTargets = ixdsReferences.get(TARGET_UKFRS, [])
    if len(foundTargets) > 1:
        yield Validation.error(
            codes="ESEF.UKFRC5.multipleEntryPoints",
            msg=_(
                'UKSEF reports MUST have a single targeted element with the "UKFRS" target. '
                "Multiple matching ix:references elements were found in the report."
            ),
            modelObject=foundTargets,
        )

    elif len(foundTargets) == 1:
        uksefSchemaRefs = pluginData.getUksefSchemaRefs(foundTargets)
        if len(uksefSchemaRefs) > 1:
            yield Validation.error(
                codes="ESEF.UKFRC1.multipleEntryPoints",
                msg=_(
                    'UKSEF reports MUST have a single schemaRef in a "UKFRS" targeted ix:references element. '
                    "Multiple matching schemaRefs were found in the report."
                ),
                modelObject=uksefSchemaRefs,
            )


@validation(
    # using FINALLY hook to ensure that the ixdsReferences are fully populated before checking for the UKFRS target
    hook=ValidationHook.FINALLY,
)
def rule_targetAttributeUsedForESEFContents(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC4: In accordance with the ESEF Reporting Manual, Rule 2.5.3, 'All [ESEF] tagged data MUST
    be in the "default" target XBRL document'. ESEF tagged data MUST NOT carry a target attribute.
    """
    if val.authority != AUTHORITY_UKFRC or not pluginData.isUkfrsTarget(val.modelXbrl):
        return

    if ixdsReferences := getattr(val, "ixdsReferences", None):
        ESEFTargets = ixdsReferences.get(None, [])
        if not ESEFTargets:
            yield Validation.error(
                codes="ESEF.UKFRC4.targetAttributeUsedForESEFContents",
                msg=_(
                    "ESEF tagged data MUST be in the default (unnamed) target XBRL document and "
                    "MUST NOT carry a target attribute. No matching ix:references element was found in the report."
                ),
            )

    invalidTargetElts: list[ModelObject] = []
    invalidTargetValues: set[str] = set()

    for ixdsHtmlRootElt in val.modelXbrl.ixdsHtmlElements or ():
        ns = getattr(ixdsHtmlRootElt.modelDocument, "ixNS", ixbrl11)
        allowedTags = _ixTagsForNamespace(ns, _TARGET_ALLOWED_LOCAL_NAMES)
        disallowedTags = _ixTagsForNamespace(ns, _TARGET_DISALLOWED_LOCAL_NAMES)

        otherNs = ixbrl if ns == ixbrl11 else ixbrl11
        allowedTags += _ixTagsForNamespace(otherNs, _TARGET_ALLOWED_LOCAL_NAMES)
        disallowedTags += _ixTagsForNamespace(otherNs, _TARGET_DISALLOWED_LOCAL_NAMES)

        for elt in ixdsHtmlRootElt.iter(*allowedTags, *disallowedTags):
            tag = getattr(elt, "tag", None)
            if not isinstance(tag, str) or "target" not in elt.attrib:
                continue

            targetValue = elt.get("target") or ""
            if tag in allowedTags and targetValue == TARGET_UKFRS:
                continue

            if tag in disallowedTags:
                invalidTargetElts.append(elt)
                invalidTargetValues.add(targetValue)

    if invalidTargetElts:
        yield Validation.error(
            codes="ESEF.UKFRC4.targetAttributeUsedForESEFContents",
            msg=_(
                "ESEF tagged data MUST be in the default (unnamed) target XBRL document and "
                "MUST NOT carry a target attribute. Found target attribute value(s): %(targets)s."
            ),
            modelObject=invalidTargetElts,
            targets=", ".join(sorted(f'"{value}"' for value in invalidTargetValues)),
        )


@validation(
    # using FINALLY hook to ensure that the ixdsReferences are fully populated before checking for the UKFRS target
    hook=ValidationHook.FINALLY,
)
def rule_noUKFRSData(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC5: In a UKSEF report, there should be two ix:references containers – one should contain the
    schemaRef for the issuer’s private extension as per ESEF requirements and MUST omit the target.
    The other must contain a UKSEF schemaRef with the "UKFRS" target attribute.
    """
    if val.authority != AUTHORITY_UKFRC:
        return

    if ixdsReferences := getattr(val, "ixdsReferences", None):
        if not ixdsReferences.get(TARGET_UKFRS, []):
            yield Validation.error(
                codes="ESEF.UKFRC5.noUKFRSData",
                msg=_(
                    'UKSEF reports MUST have a "UKFRS" targeted ix:references element. '
                    'No matching ix:references element was found in the report.'
                ),
            )


@validation(
    # using FINALLY hook to ensure that the ixdsReferences are fully populated before checking for the UKFRS target
    hook=ValidationHook.FINALLY,
)
def rule_noESEFData(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC5: In a UKSEF report, there should be two ix:references containers – one should contain the
    schemaRef for the issuer’s private extension as per ESEF requirements and MUST omit the target.
    The other must contain a UKSEF schemaRef with the "UKFRS" target attribute.
    """
    if val.authority != AUTHORITY_UKFRC:
        return

    if ixdsReferences := getattr(val, "ixdsReferences", None):
        if not ixdsReferences.get(None, []):
            yield Validation.error(
                codes="ESEF.UKFRC5.noESEFData",
                msg=_(
                    "UKSEF reports MUST have an default (unnamed) targeted ix:references element. "
                    "No matching ix:references element was found in the report."
                ),
            )
