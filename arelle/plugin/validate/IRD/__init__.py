"""
See COPYRIGHT.md for copyright information.

Hong Kong IRD Profits Tax iXBRL Validation Plugin.

Implements the IRD's published NVAD and technical validation rules for
BIR51 and BIR52 Profits Tax iXBRL filings.

Plugin entry point — loaded by Arelle via --plugin plugin/validate/IRD.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from arelle.Version import authorLabel, copyrightLabel

from .ValidationPluginExtension import ValidationPluginExtension
from .rules import (
    nvad_structural,
)

PLUGIN_NAME = "Validate IRD"
DISCLOSURE_SYSTEM_VALIDATION_TYPE = "IRD"

CONFIG_PATH = Path(__file__).parent / "resources" / "config.xml"
validationPlugin = ValidationPluginExtension(
    name=PLUGIN_NAME,
    disclosureSystemConfigUrl=CONFIG_PATH,
    validationTypes=[DISCLOSURE_SYSTEM_VALIDATION_TYPE],
    validationRuleModules=[
        nvad_structural,
    ],
)


def disclosureSystemTypes(
    *args: Any, **kwargs: Any
) -> tuple[tuple[str, str], ...]:
    return validationPlugin.disclosureSystemTypes


def disclosureSystemConfigURL(*args: Any, **kwargs: Any) -> str:
    return validationPlugin.disclosureSystemConfigURL


def validateXbrlFinally(*args: Any, **kwargs: Any) -> None:
    return validationPlugin.validateXbrlFinally(*args, **kwargs)


__pluginInfo__ = {
    "name": PLUGIN_NAME,
    "version": "0.1.0",
    "description": (
        "Validation plugin for Hong Kong IRD Profits Tax iXBRL filings "
        "(BIR51/BIR52)."
    ),
    "import": ("inlineXbrlDocumentSet",),
    "license": "Apache-2",
    "author": authorLabel,
    "copyright": copyrightLabel,
    "DisclosureSystem.Types": disclosureSystemTypes,
    "DisclosureSystem.ConfigURL": disclosureSystemConfigURL,
    "Validate.XBRL.Finally": validateXbrlFinally,
}
