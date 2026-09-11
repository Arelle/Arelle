"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from dataclasses import dataclass

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
        """Check if the target document is a UKFRS target."""
        ixdsTarget: str | None = getattr(modelXbrl, "ixdsTarget", "")
        return ixdsTarget == TARGET_UKFRS

    def isEsefTarget(self, modelXbrl: ModelXbrl) -> bool:
        """Check if the target document is an ESEF target."""
        ixdsTarget: str | None = getattr(modelXbrl, "ixdsTarget", "")
        return ixdsTarget is None
