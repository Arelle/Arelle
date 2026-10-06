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

PUBLISHER_COUNTRY_GB = "GB"


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_nonUtf8Instance(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC20: UKSEF instance documents MUST use the UTF-8 character encoding.
    """
    modelXbrl = val.modelXbrl
    if val.authority != AUTHORITY_UKFRC or not pluginData.isEsefTarget(modelXbrl):
        return

    for ixdsHtmlRootElt in getattr(modelXbrl, "ixdsHtmlElements", ()):
        modelDocument = ixdsHtmlRootElt.modelDocument
        encoding = modelDocument.documentEncoding
        if not encoding or encoding.lower() not in ("utf-8", "utf8"):
            yield Validation.error(
                "ESEF.UKFRC20.nonUtf8Instance",
                _("UKSEF instance documents MUST use the UTF-8 character encoding: %(file)s uses %(encoding)s."),
                modelObject=modelDocument,
                file=modelDocument.basename,
                encoding=encoding,
            )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
)
def rule_ukfrc21(
        pluginData: PluginValidationDataExtension,
        val: ValidateXbrl,
        *args: Any,
        **kwargs: Any,
) -> Iterable[Validation]:
    """
    UKFRC21: UKSEF report package "publisherCountry" metadata element MUST be "GB".
    """
    modelXbrl = val.modelXbrl
    if val.authority != AUTHORITY_UKFRC or not pluginData.isEsefTarget(modelXbrl):
        return

    taxonomyPackage = modelXbrl.fileSource.taxonomyPackage if modelXbrl.fileSource else None
    if not taxonomyPackage:
        return

    publisherCountry = taxonomyPackage.get("publisherCountry")
    if not publisherCountry:
        yield Validation.error(
            "ESEF.UKFRC21.missingPublisherCountryElement",
            _('The report package metadata for a UKSEF report MUST contain a "publisherCountry" element set to "%(requiredCountry)s".'),
            modelObject=modelXbrl,
            requiredCountry=PUBLISHER_COUNTRY_GB,
        )

    elif publisherCountry != PUBLISHER_COUNTRY_GB:
        yield Validation.error(
            "ESEF.UKFRC21.invalidPublisherCountryElementContent",
            _('The "publisherCountry" element of the report package metadata for a UKSEF report MUST be set to '
              '"%(requiredCountry)s" but was "%(publisherCountry)s".'),
            modelObject=modelXbrl,
            requiredCountry=PUBLISHER_COUNTRY_GB,
            publisherCountry=publisherCountry,
        )
