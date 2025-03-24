"""
See COPYRIGHT.md for copyright information.

- [Filer Manual Guidelines](https://www.sbr-nl.nl/werken-met-sbr/taxonomie/documentatie-nederlandse-taxonomie)
- [Kamer van Koophandel Filing Rules - NT19](https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20240801%20KvK%20Filing%20Rules%20NT19%20v1_0.pdf)
- [SBR Filing Rules - NT19](https://www.sbr-nl.nl/sites/default/files/bestanden/taxonomie/20240301%20SBR%20Filing%20Rules%20NT19.pdf)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.ModelDocument import LoadingException, ModelDocument
from arelle.Version import authorLabel, copyrightLabel
from .ValidationPluginExtension import ValidationPluginExtension

PLUGIN_NAME = "Validate NL iXBRL"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "NL-iXBRL"


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def modelXbrlLoadComplete(*args: Any, **kwargs: Any) -> ModelDocument | LoadingException | None:
    return validationPlugin.modelXbrlLoadComplete(*args, **kwargs)


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Validation plugin for the Inline Netherlands taxonomies.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "ModelXbrl.LoadComplete": modelXbrlLoadComplete,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
