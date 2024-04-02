"""
See COPYRIGHT.md for copyright information.

Filer Manual Guidelines: https://danishbusinessauthority.dk/sites/default/files/2023-10/xbrl-taxonomy-framework-architecture-01102015_wa.pdf
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.Version import authorLabel, copyrightLabel
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import fr

PLUGIN_NAME = "Validate DBA"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "DBA"


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[fr],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.0.1",
    "description": "Validation plugin for DBA (Danish Business Authority) taxonomies.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
