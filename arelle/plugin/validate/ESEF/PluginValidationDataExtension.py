"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from arelle.ModelInstanceObject import ModelContext
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData
from arelle.utils.validate.ContextIssues import ContextIssues, getContextIssues, getContextsByEntityIdentifier
from .Const import TARGET_UKFRS


@dataclass
class PluginValidationDataExtension(PluginData):

    def getContextIssues(self, modelXbrl: ModelXbrl) -> ContextIssues:
        return getContextIssues(modelXbrl)

    def getContextsByEntityIdentifier(self, modelXbrl: ModelXbrl) -> dict[tuple[str, str], list[ModelContext]]:
        return getContextsByEntityIdentifier(modelXbrl)

    def isUkfrsTarget(self, modelXbrl: ModelXbrl) -> bool:
        if not hasattr(modelXbrl, "ixdsTarget"):
            return False
        return cast(str | None, modelXbrl.ixdsTarget) == TARGET_UKFRS
