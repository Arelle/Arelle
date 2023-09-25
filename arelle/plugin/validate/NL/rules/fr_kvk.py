"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable

from arelle import ModelDocument
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import (
    DISCLOSURE_SYSTEM_NT16,
    DISCLOSURE_SYSTEM_NT17,
)
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    disclosureSystems=[
        DISCLOSURE_SYSTEM_NT16,
        DISCLOSURE_SYSTEM_NT17,
    ],
)
def rule_fr_kvk_1_01(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    """
    FR-KVK-1.01: An XBRL instance document MUST have the file extension .xbrl
    """
    modelXbrl = val.modelXbrl
    for doc in modelXbrl.urlDocs.values():
        if doc.type == ModelDocument.Type.INSTANCE:
            if not doc.basename.endswith('.xbrl'):
                yield Validation.error(
                    codes='NL.FR-KVK-1.01',
                    msg=_('An XBRL instance document MUST have the file extension .xbrl: %(fileName)s'),
                    modelObject=doc,
                    fileName=doc.basename,
                )
