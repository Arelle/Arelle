"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any, Iterable

from arelle import XbrlConst
from arelle.ModelDocument import ModelDocument, Type as ModelDocumentType
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.PluginHooks import ValidationHook
from arelle.utils.validate.Decorator import validation
from arelle.utils.validate.Validation import Validation
from ..DisclosureSystems import DISCLOSURE_SYSTEM_2022
from ..PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


@validation(hook=ValidationHook.XBRL_DTS_DOCUMENT)
def rule02_01(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    modelDocument: ModelDocument,
    isFilingDocument: bool,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    if (
        modelDocument.type == ModelDocumentType.SCHEMA
        and modelDocument.targetNamespace is not None
        and len(modelDocument.targetNamespace) > 100
    ):
        yield Validation.error(
            codes="XYZ.02.01",
            msg=_("TargetNamespace is too long %(namespace)s."),
            modelObject=val.modelXbrl,
            namespace=modelDocument.targetNamespace,
        )


@validation(
    hook=ValidationHook.XBRL_FINALLY,
    excludeDisclosureSystems=DISCLOSURE_SYSTEM_2022,
)
def rule02_02(
    pluginData: PluginValidationDataExtension,
    val: ValidateXbrl,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Validation] | None:
    if val.modelXbrl.relationshipSet(XbrlConst.summationItem):
        yield Validation.error(
            codes="XYZ.02.02",
            msg=_("XBRL 2.1 calculations detected. XYZ 2023 taxonomy requires calc 1.1."),
            modelObject=val.modelXbrl,
        )
