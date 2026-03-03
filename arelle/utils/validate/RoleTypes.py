from __future__ import annotations

from arelle.ModelDtsObject import ModelRoleType
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.validate.Common import isExtensionUri


def getExtensionRoleTypes(
        modelXbrl: ModelXbrl,
        taxonomyUrlPrefixes: frozenset[str]
) -> list[ModelRoleType]:
    """
    Returns a list of extension role types in the DTS.
    """
    return [
        roleType
        for roleTypes in modelXbrl.roleTypes.values()
        for roleType in roleTypes
        if isExtensionUri(roleType.document.uri, modelXbrl, taxonomyUrlPrefixes)
    ]
