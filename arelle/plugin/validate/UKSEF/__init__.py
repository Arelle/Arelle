"""
See COPYRIGHT.md for copyright information.

UK Single Electronic Format (UKSEF) validation plugin.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.Version import authorLabel, copyrightLabel
from .ValidationPluginExtension import ValidationPluginExtension
from .rules import context, document, entity, mandatory, package, target, taxonomy

PLUGIN_NAME = "Validate UKSEF"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "UKSEF"


validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[taxonomy, target, entity, context, package, document, mandatory],
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
    "description": "Validation plugin for UK Single Electronic Format (UKSEF) filings.",
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
