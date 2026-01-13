from __future__ import annotations

from arelle.ModelDtsObject import ModelConcept
from arelle.ModelXbrl import ModelXbrl


def isExtensionUri(uri: str, modelXbrl: ModelXbrl, taxonomyUrlPrefixes: frozenset[str]) -> bool:
    if uri.startswith(modelXbrl.uriDir):
        return True
    return not any(uri.startswith(taxonomyUri) for taxonomyUri in taxonomyUrlPrefixes)

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
