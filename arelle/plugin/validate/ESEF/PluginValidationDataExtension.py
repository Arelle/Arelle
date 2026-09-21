"""
See COPYRIGHT.md for copyright information.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from arelle import XbrlConst
from arelle.ModelInstanceObject import ModelContext
from arelle.ModelObject import ModelObject
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.PluginData import PluginData
from arelle.utils.validate.ContextIssues import ContextIssues, getContextIssues, getContextsByEntityIdentifier
from .Const import TARGET_UKFRS, UKSEF_ENTRY_POINT_PATTERN

_LINK_SCHEMA_REF = f"{{{XbrlConst.link}}}schemaRef"
_XLINK_HREF = f"{{{XbrlConst.xlink}}}href"


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

    def isEsefTarget(self, modelXbrl: ModelXbrl) -> bool:
        """Check if the target document is an ESEF target."""
        ixdsTarget: str | None = getattr(modelXbrl, "ixdsTarget", "")
        return ixdsTarget is None

    def getUksefSchemaRefs(self, targetIxReferences: Iterable[ModelObject]) -> list[ModelObject]:
        """
        Retrieves UKSEF Schema References from the given iterable of ModelObject instances.

        Finds and collects all schema references within the descendants of the provided
        ModelObject elements that match a specific UKSEF entry point pattern.

        Args:
            targetIxReferences: An iterable collection of ModelObject elements to search for schema references.

        Returns:
            A list of ModelObject instances representing schema references that match
            the UKSEF entry point pattern.
        """
        uksefSchemaRefs: list[ModelObject] = []
        for referencesElt in targetIxReferences:
            for schemaRef in referencesElt.iterdescendants(tag=_LINK_SCHEMA_REF):
                href = schemaRef.get(_XLINK_HREF, "").strip()

                if UKSEF_ENTRY_POINT_PATTERN.match(href):
                    uksefSchemaRefs.append(schemaRef)

        return uksefSchemaRefs
