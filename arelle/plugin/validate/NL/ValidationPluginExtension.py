"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.ModelXbrl import ModelXbrl
from arelle.typing import TypeGetText
from arelle.utils.validate.ValidationPlugin import ValidationPlugin
from .PluginValidationDataExtension import PluginValidationDataExtension

_: TypeGetText


class ValidationPluginExtension(ValidationPlugin):
    def newPluginData(self) -> PluginValidationDataExtension:
        return PluginValidationDataExtension(self.name)
