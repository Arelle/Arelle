"""
An example Arelle validation plugin, published on arelle.org.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.utils.validate.ValidationPlugin import ValidationPlugin

from . import house_rules

PLUGIN_NAME = "House rules"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "HOUSE"

validationPlugin = ValidationPlugin(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=Path(__file__).parent / "resources" / "config.xml",
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[house_rules],
)


def disclosureSystemTypes(*args: Any, **kwargs: Any) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def validateXbrlStart(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlStart(*args, **kwargs)


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "1.0",
    "description": "Example house rules published on arelle.org.",
    "license": "Apache-2",
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "Validate.XBRL.Start": validateXbrlStart,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
