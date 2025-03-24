"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelXbrl import ModelXbrl
from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(self.name)

    def modelDocumentPullLoader(
        self,
        modelXbrl: ModelXbrl,
        normalizedUri: str,
        filepath: str,
        isEntry: bool,
        namespace: str | None,
        *args: Any,
        **kwargs: Any,
    ) -> ModelDocument | LoadingException | None:
        if self.disclosureSystemFromPluginSelected(modelXbrl):
            return LoadingException(_("XYZ validation plugin is a template for new validation plugins and shouldn't be used directly."))
        return None

    def modelXbrlLoadComplete(
        self,
        modelXbrl: ModelXbrl,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if self.disclosureSystemFromPluginSelected(modelXbrl):
            if modelXbrl.modelDocument is None:
                modelXbrl.error(
                    codes="XYZ.01.01",
                    msg=_("An XBRL Report Package is required but could not be loaded"),
                    modelObject=modelXbrl,
                )
        return None
