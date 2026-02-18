from __future__ import annotations

from arelle.ModelXbrl import ModelXbrl


def isExtensionUri(uri: str, modelXbrl: ModelXbrl, taxonomyUrlPrefixes: frozenset[str]) -> bool:
    if uri.startswith(modelXbrl.uriDir):
        return True
    return not any(uri.startswith(taxonomyUri) for taxonomyUri in taxonomyUrlPrefixes)
