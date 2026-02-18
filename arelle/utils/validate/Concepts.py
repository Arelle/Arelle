from __future__ import annotations

from arelle.ModelDtsObject import ModelConcept
from arelle.ModelXbrl import ModelXbrl
from arelle.utils.validate.Common import isExtensionUri


def getExtensionConcepts(modelXbrl: ModelXbrl, taxonomyUrlPrefixes: frozenset[str]) -> list[ModelConcept]:
    """
    Returns a list of extension concepts in the DTS.
    """
    extensionConcepts = []
    for concepts in modelXbrl.nameConcepts.values():
        for concept in concepts:
            if isExtensionUri(concept.document.uri, modelXbrl, taxonomyUrlPrefixes):
                extensionConcepts.append(concept)
    return extensionConcepts
