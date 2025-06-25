"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle.ValidateXbrl import ValidateXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .DisclosureSystems import DISCLOSURE_SYSTEM_EDINET
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self, validateXbrl: ValidateXbrl) -> PluginValidationDataExtension:
        disclosureSystem = validateXbrl.disclosureSystem.name
        if disclosureSystem == DISCLOSURE_SYSTEM_EDINET:
            pass
        else:
            raise ValueError(f'Invalid EDINET disclosure system: {disclosureSystem}')
        return PluginValidationDataExtension(
            self.name,
        )

    def modelXbrlLoadComplete(self, *args: Any, **kwargs: Any) -> None:
        return None
